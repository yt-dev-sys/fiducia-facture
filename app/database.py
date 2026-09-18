"""
Database layer for the Facture App.
Uses SQLite. All access goes through the functions in this module -
no raw SQL should be written elsewhere in the app.
"""

import sqlite3
import os
from datetime import date

from app.app_paths import get_database_path, migrate_legacy_user_files
from app.migrations import migrate

DB_PATH = str(get_database_path())


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    # timeout: if the file is briefly locked by another connection (e.g. the
    # daily Telegram backup thread reading it at the same moment a UI action
    # writes to it), retry for up to 10s instead of failing immediately with
    # "database is locked". WAL mode lets that backup's read connection run
    # concurrently with writes here rather than blocking on the same lock.
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    migrate_legacy_user_files()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS company_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            business_type TEXT NOT NULL DEFAULT 'company',  -- 'auto' or 'company'
            name TEXT DEFAULT '',
            address TEXT DEFAULT '',
            ice TEXT DEFAULT '',
            if_number TEXT DEFAULT '',
            rc TEXT DEFAULT '',
            patente TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            default_tva_rate REAL DEFAULT 20.0,
            cnss TEXT DEFAULT '',
            bank_details TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT DEFAULT '',
            ice TEXT DEFAULT '',
            if_number TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (date('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT DEFAULT (date('now'))
        )
    """)

    # Legacy table, kept only so we can migrate old client<->service links below.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS client_services (
            client_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            PRIMARY KEY (client_id, service_id),
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS client_service_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            service_id INTEGER,
            description TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoice_counters (
            year INTEGER PRIMARY KEY,
            next_number INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE,
            invoice_date TEXT NOT NULL,
            client_id INTEGER NOT NULL,
            business_type TEXT NOT NULL,          -- snapshot at creation time
            tva_rate REAL NOT NULL DEFAULT 0,      -- 0 if auto-entrepreneur
            subtotal_ht REAL NOT NULL DEFAULT 0,
            tva_amount REAL NOT NULL DEFAULT 0,
            total_ttc REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'unpaid', -- 'unpaid' or 'paid'
            deadline TEXT DEFAULT 'Immédiat',
            payment_type TEXT DEFAULT '',
            payment_date TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (date('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            service_id INTEGER,
            description TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL DEFAULT 0,
            line_total REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Ensure a single company_profile row exists
    cur.execute("SELECT COUNT(*) FROM company_profile")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO company_profile (id, business_type) VALUES (1, 'company')")

    # Migration: older databases created before "if_number" existed on clients
    # (it used to be called "cnss"). Rename the column so existing data is kept.
    existing_client_columns = [row["name"] for row in cur.execute("PRAGMA table_info(clients)").fetchall()]
    if "cnss" in existing_client_columns and "if_number" not in existing_client_columns:
        cur.execute("ALTER TABLE clients RENAME COLUMN cnss TO if_number")
    elif "if_number" not in existing_client_columns:
        cur.execute("ALTER TABLE clients ADD COLUMN if_number TEXT DEFAULT ''")

    # Migration: carry over old client<->service links (no price) into the new
    # client_service_prices table, with price defaulting to 0, the first time we see them.
    old_links = cur.execute("SELECT client_id, service_id FROM client_services").fetchall()
    already_migrated = cur.execute("SELECT COUNT(*) FROM client_service_prices").fetchone()[0]
    if old_links and already_migrated == 0:
        for link in old_links:
            svc = cur.execute("SELECT name FROM services WHERE id = ?", (link["service_id"],)).fetchone()
            svc_name = svc["name"] if svc else "Service"
            cur.execute(
                "INSERT INTO client_service_prices (client_id, service_id, description, price) VALUES (?, ?, ?, 0)",
                (link["client_id"], link["service_id"], svc_name)
            )

    # Migration: older databases created before "deadline" existed on invoices.
    existing_invoice_columns = [row["name"] for row in cur.execute("PRAGMA table_info(invoices)").fetchall()]
    if "deadline" not in existing_invoice_columns:
        cur.execute("ALTER TABLE invoices ADD COLUMN deadline TEXT DEFAULT 'Immédiat'")

    # Migration: rebuild the invoices table so "numero" is nullable. A facture now
    # starts as a draft with numero = NULL in "List SF"; it only receives its
    # permanent sequential number once promoted ("Facturer") into the Factures tab.
    #
    # IMPORTANT: SQLite rewrites foreign keys when a referenced table is renamed.
    # If invoice_items references invoices, renaming invoices to invoices_old makes
    # invoice_items reference invoices_old. Dropping invoices_old then leaves a
    # broken FK and the next INSERT into invoice_items fails with:
    #   no such table: main/invoices_old
    # Some older builds used the singular name invoice_old, so we repair both forms.
    numero_col = next((c for c in cur.execute("PRAGMA table_info(invoices)").fetchall() if c["name"] == "numero"), None)
    if numero_col is not None and numero_col["notnull"]:
        cur.execute("ALTER TABLE invoices RENAME TO invoices_old")

        cur.execute("""
            CREATE TABLE invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE,
                invoice_date TEXT NOT NULL,
                client_id INTEGER NOT NULL,
                business_type TEXT NOT NULL,
                tva_rate REAL NOT NULL DEFAULT 0,
                subtotal_ht REAL NOT NULL DEFAULT 0,
                tva_amount REAL NOT NULL DEFAULT 0,
                total_ttc REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'unpaid',
                deadline TEXT DEFAULT 'Immédiat',
                payment_type TEXT DEFAULT '',
                payment_date TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT (date('now')),
                FOREIGN KEY (client_id) REFERENCES clients(id)
            )
        """)

        # Copy the invoices first because the rebuilt invoice_items table will
        # immediately enforce its FK against the new invoices table.
        cur.execute("""
            INSERT INTO invoices (id, numero, invoice_date, client_id, business_type, tva_rate,
                                   subtotal_ht, tva_amount, total_ttc, status, deadline,
                                   payment_type, payment_date, notes, created_at)
            SELECT id, numero, invoice_date, client_id, business_type, tva_rate,
                   subtotal_ht, tva_amount, total_ttc, status, deadline,
                   payment_type, payment_date, notes, created_at
            FROM invoices_old
        """)

        # Rebuild invoice_items BEFORE dropping invoices_old so there is never a
        # moment where invoice_items has a foreign key to a table that no longer
        # exists. This is also safe for databases produced by the broken migration.
        invoice_items_fks = cur.execute("PRAGMA foreign_key_list(invoice_items)").fetchall()
        old_invoice_fk = next((fk for fk in invoice_items_fks
                               if fk["table"] in ("invoices_old", "invoice_old")), None)
        if old_invoice_fk:
            cur.execute("ALTER TABLE invoice_items RENAME TO invoice_items_old")
            cur.execute("""
                CREATE TABLE invoice_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL,
                    service_id INTEGER,
                    description TEXT NOT NULL,
                    quantity REAL NOT NULL DEFAULT 1,
                    unit_price REAL NOT NULL DEFAULT 0,
                    line_total REAL NOT NULL DEFAULT 0,
                    source_price_id INTEGER,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                    FOREIGN KEY (service_id) REFERENCES services(id)
                )
            """)
            old_item_columns = {row["name"] for row in cur.execute("PRAGMA table_info(invoice_items_old)").fetchall()}
            source_price_expr = "source_price_id" if "source_price_id" in old_item_columns else "NULL"
            cur.execute(f"""
                INSERT INTO invoice_items (id, invoice_id, service_id, description, quantity,
                                            unit_price, line_total, source_price_id)
                SELECT id, invoice_id, service_id, description, quantity,
                       unit_price, line_total, {source_price_expr}
                FROM invoice_items_old
            """)
            cur.execute("DROP TABLE invoice_items_old")

        cur.execute("DROP TABLE invoices_old")

    # Migration: older databases created before "cnss" / "bank_details" existed on company_profile.
    existing_profile_columns = [row["name"] for row in cur.execute("PRAGMA table_info(company_profile)").fetchall()]
    if "cnss" not in existing_profile_columns:
        cur.execute("ALTER TABLE company_profile ADD COLUMN cnss TEXT DEFAULT ''")
    if "bank_details" not in existing_profile_columns:
        cur.execute("ALTER TABLE company_profile ADD COLUMN bank_details TEXT DEFAULT ''")

    # Migration: older invoice_items tables created before "source_price_id" existed
    # (used to trace a snapshotted line item back to the client_service_prices row
    # it was checked from, so the edit form can pre-check the right boxes).
    existing_item_columns = [row["name"] for row in cur.execute("PRAGMA table_info(invoice_items)").fetchall()]
    if "source_price_id" not in existing_item_columns:
        cur.execute("ALTER TABLE invoice_items ADD COLUMN source_price_id INTEGER")

    # Repair databases already affected by the old migration. Depending on the
    # application version that created the database, the dangling FK may point to
    # either invoices_old or invoice_old (singular). Rebuild invoice_items so it
    # references the real invoices table.
    invoice_items_fks = cur.execute("PRAGMA foreign_key_list(invoice_items)").fetchall()
    if any(fk["table"] in ("invoices_old", "invoice_old") for fk in invoice_items_fks):
        cur.execute("ALTER TABLE invoice_items RENAME TO invoice_items_old")
        cur.execute("""
            CREATE TABLE invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                service_id INTEGER,
                description TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL DEFAULT 0,
                line_total REAL NOT NULL DEFAULT 0,
                source_price_id INTEGER,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        """)
        old_item_columns = {row["name"] for row in cur.execute("PRAGMA table_info(invoice_items_old)").fetchall()}
        source_price_expr = "source_price_id" if "source_price_id" in old_item_columns else "NULL"
        cur.execute(f"""
            INSERT INTO invoice_items (id, invoice_id, service_id, description, quantity,
                                        unit_price, line_total, source_price_id)
            SELECT id, invoice_id, service_id, description, quantity,
                   unit_price, line_total, {source_price_expr}
            FROM invoice_items_old
        """)
        cur.execute("DROP TABLE invoice_items_old")



    # One-time migration: renumber every existing invoice to the current "SEQ-YEAR"
    # format (3-digit sequence), in chronological order per year, and reset each
    # year's counter accordingly so future invoices continue seamlessly.
    already_renumbered = cur.execute(
        "SELECT value FROM app_meta WHERE key = 'numero_format_v2_migrated'"
    ).fetchone()
    if already_renumbered is None:
        years = [row["y"] for row in cur.execute(
            "SELECT DISTINCT strftime('%Y', invoice_date) AS y FROM invoices"
        ).fetchall() if row["y"]]
        for y in years:
            year_int = int(y)
            invs = cur.execute(
                "SELECT id FROM invoices WHERE strftime('%Y', invoice_date) = ? "
                "ORDER BY invoice_date ASC, id ASC", (y,)
            ).fetchall()
            for i, inv in enumerate(invs, start=1):
                cur.execute(
                    "UPDATE invoices SET numero = ? WHERE id = ?",
                    (f"{i:03d}-{year_int}", inv["id"])
                )
            cur.execute(
                "INSERT INTO invoice_counters (year, next_number) VALUES (?, ?) "
                "ON CONFLICT(year) DO UPDATE SET next_number = excluded.next_number",
                (year_int, len(invs) + 1)
            )
        cur.execute(
            "INSERT INTO app_meta (key, value) VALUES ('numero_format_v2_migrated', '1')"
        )

    # Migration: add reserved_numero to preserve a number across unfinalize/re-finalize
    # cycles so that défacturé invoices recover their original number on re-facturation.
    existing_invoice_columns = [row["name"] for row in cur.execute("PRAGMA table_info(invoices)").fetchall()]
    if "reserved_numero" not in existing_invoice_columns:
        cur.execute("ALTER TABLE invoices ADD COLUMN reserved_numero TEXT DEFAULT NULL")

    # Adopt the completed legacy-compatible schema as explicit schema version 1.
    # Future versions must add transactional migrations in app/migrations.py.
    migrate(conn)
    conn.commit()
    conn.close()


# ---------------- Company profile ----------------

def get_company_profile():
    conn = get_connection()
    row = conn.execute("SELECT * FROM company_profile WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else None


def update_company_profile(data: dict):
    conn = get_connection()
    conn.execute("""
        UPDATE company_profile SET
            business_type = ?, name = ?, address = ?, ice = ?, if_number = ?,
            rc = ?, patente = ?, phone = ?, email = ?, default_tva_rate = ?,
            cnss = ?, bank_details = ?
        WHERE id = 1
    """, (
        data.get("business_type", "company"),
        data.get("name", ""),
        data.get("address", ""),
        data.get("ice", ""),
        data.get("if_number", ""),
        data.get("rc", ""),
        data.get("patente", ""),
        data.get("phone", ""),
        data.get("email", ""),
        data.get("default_tva_rate", 20.0),
        data.get("cnss", ""),
        data.get("bank_details", ""),
    ))
    conn.commit()
    conn.close()


# ---------------- Clients ----------------

def list_clients(search: str = ""):
    conn = get_connection()
    query = """
        SELECT clients.*,
               GROUP_CONCAT(client_service_prices.description, char(10)) as service_names,
               COALESCE(SUM(client_service_prices.price), 0) as total_price
        FROM clients
        LEFT JOIN client_service_prices ON client_service_prices.client_id = clients.id
    """
    params = []
    if search:
        query += " WHERE clients.name LIKE ? OR clients.ice LIKE ?"
        params += [f"%{search}%", f"%{search}%"]
    query += " GROUP BY clients.id ORDER BY clients.name"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_client(client_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_client_service_prices(client_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, service_id, description, price FROM client_service_prices WHERE client_id = ? ORDER BY id",
        (client_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _set_client_service_prices(conn, client_id, rows):
    """rows: list of dicts {service_id, description, price}. Replaces all existing rows for this client."""
    conn.execute("DELETE FROM client_service_prices WHERE client_id = ?", (client_id,))
    for row in rows or []:
        conn.execute(
            "INSERT INTO client_service_prices (client_id, service_id, description, price) VALUES (?, ?, ?, ?)",
            (client_id, row.get("service_id"), row["description"], row.get("price", 0.0))
        )


def create_client(name, address="", ice="", if_number="", phone="", email="", service_price_rows=None):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO clients (name, address, ice, if_number, phone, email) VALUES (?, ?, ?, ?, ?, ?)",
        (name, address, ice, if_number, phone, email)
    )
    new_id = cur.lastrowid
    _set_client_service_prices(conn, new_id, service_price_rows)
    conn.commit()
    conn.close()
    return new_id


def update_client(client_id, name, address="", ice="", if_number="", phone="", email="", service_price_rows=None):
    conn = get_connection()
    conn.execute(
        "UPDATE clients SET name=?, address=?, ice=?, if_number=?, phone=?, email=? WHERE id=?",
        (name, address, ice, if_number, phone, email, client_id)
    )
    _set_client_service_prices(conn, client_id, service_price_rows)
    conn.commit()
    conn.close()


def get_client_service_price_sum(client_id):
    conn = get_connection()
    total = conn.execute(
        "SELECT COALESCE(SUM(price), 0) FROM client_service_prices WHERE client_id = ?", (client_id,)
    ).fetchone()[0]
    conn.close()
    return total


def delete_client(client_id):
    conn = get_connection()
    # Prevent deleting a client that has invoices, to preserve accounting integrity
    count = conn.execute("SELECT COUNT(*) FROM invoices WHERE client_id = ?", (client_id,)).fetchone()[0]
    if count > 0:
        conn.close()
        raise ValueError("Impossible de supprimer ce client : des factures existent pour ce client.")
    conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()


# ---------------- Services ----------------

def list_services(search: str = ""):
    conn = get_connection()
    if search:
        rows = conn.execute(
            "SELECT * FROM services WHERE name LIKE ? ORDER BY name", (f"%{search}%",)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM services ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_service(service_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_service(name, description=""):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO services (name, description) VALUES (?, ?)",
        (name, description)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_service(service_id, name, description=""):
    conn = get_connection()
    conn.execute(
        "UPDATE services SET name=?, description=? WHERE id=?",
        (name, description, service_id)
    )
    conn.commit()
    conn.close()


def delete_service(service_id):
    conn = get_connection()
    conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
    conn.commit()
    conn.close()


# ---------------- Invoices ----------------

def _next_sequence_order(conn, year: int):
    """Returns the next never-reused "sequence_order" slot for the given year. This is
    the invoice's permanent home position (it decides relative order - who was finalized
    before whom) and is completely separate from its displayed numero, which is
    recomputed gapless by _resequence_year() below."""
    row = conn.execute("SELECT next_number FROM invoice_counters WHERE year = ?", (year,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO invoice_counters (year, next_number) VALUES (?, 2)", (year,))
        seq = 1
    else:
        seq = row["next_number"]
        conn.execute("UPDATE invoice_counters SET next_number = next_number + 1 WHERE year = ?", (year,))
    return seq


def _resequence_year(conn, year: int):
    """Recomputes numero for every currently-finalized invoice of the given year, in
    order of sequence_order, so the displayed numbers are always a gapless
    001-YEAR, 002-YEAR, ... with no holes left by défacturation or deletion.
    Invoices that aren't finalized (numero IS NULL) are untouched and have no
    sequence_order of their own - they get a brand new one, at the end, whenever
    they're finalized (see finalize_invoice)."""
    rows = conn.execute(
        "SELECT id FROM invoices WHERE numero IS NOT NULL AND strftime('%Y', invoice_date) = ? "
        "ORDER BY sequence_order ASC",
        (f"{year:04d}",)
    ).fetchall()
    # Two passes: numero has a UNIQUE constraint that's checked immediately (not
    # deferred), so renumbering in place can momentarily collide with another row's
    # current value (e.g. two invoices swapping 001/002). Clearing them all first
    # avoids that - this all happens inside one uncommitted transaction so no other
    # connection ever observes the intermediate NULLs.
    for row in rows:
        conn.execute("UPDATE invoices SET numero = NULL WHERE id = ?", (row["id"],))
    for rank, row in enumerate(rows, start=1):
        conn.execute(
            "UPDATE invoices SET numero = ? WHERE id = ?",
            (f"{rank:03d}-{year}", row["id"])
        )


def create_invoice(client_id, business_type, tva_rate, deadline="Immédiat", invoice_date=None, notes="", selected_items=None):
    """Creates a DRAFT invoice for a client (numero = NULL). Drafts live in "List SF"
    and are not yet official, numbered factures. selected_items is a list of dicts
    {description, price, source_price_id} - the checked rows from the invoice
    form's services checklist - snapshotted permanently onto this invoice at
    creation time (invoice_items), immune to later edits of the client's prices."""
    if invoice_date is None:
        invoice_date = date.today().isoformat()

    if business_type != "company":
        tva_rate = 0.0

    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO invoices
                (numero, invoice_date, client_id, business_type, tva_rate,
                 subtotal_ht, tva_amount, total_ttc, status, deadline, notes)
            VALUES (NULL, ?, ?, ?, ?, 0, 0, 0, 'unpaid', ?, ?)
        """, (invoice_date, client_id, business_type, tva_rate, deadline, notes))
        invoice_id = cur.lastrowid
        _set_invoice_items(conn, invoice_id, selected_items)
        _recompute_and_store_totals(conn, invoice_id)
        conn.commit()
        return invoice_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def finalize_invoice(invoice_id):
    """Promotes a draft (numero = NULL) into an official, numbered facture.
    A fresh sequence_order slot is assigned every time an invoice is finalized -
    including a re-facturation after a défacturation - so it's always placed at
    the end of the current sequence rather than reserving/restoring an old spot.
    The displayed numero is then recomputed for the whole year via
    _resequence_year() so it's always gapless. Returns the numero. No-op if the
    invoice already has one."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT numero, invoice_date FROM invoices WHERE id = ?",
            (invoice_id,)
        ).fetchone()
        if row is None:
            return None
        if row["numero"]:
            return row["numero"]
        year = int(row["invoice_date"].split("-")[0])
        seq = _next_sequence_order(conn, year)
        conn.execute("UPDATE invoices SET sequence_order = ? WHERE id = ?", (seq, invoice_id))
        # Temporary placeholder just to mark this row "finalized" (numero NOT NULL) so
        # _resequence_year picks it up; it's immediately overwritten with the real,
        # gapless number below.
        conn.execute("UPDATE invoices SET numero = ? WHERE id = ?", (f"TMP-{invoice_id}", invoice_id))
        _resequence_year(conn, year)
        conn.commit()
        numero = conn.execute("SELECT numero FROM invoices WHERE id = ?", (invoice_id,)).fetchone()["numero"]
        return numero
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _set_invoice_items(conn, invoice_id, selected_items):
    """Replaces all invoice_items for this invoice with the given selection.
    selected_items: list of dicts {description, price, source_price_id}."""
    conn.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    for item in selected_items or []:
        price = item.get("price", 0.0)
        conn.execute("""
            INSERT INTO invoice_items
                (invoice_id, service_id, description, quantity, unit_price, line_total, source_price_id)
            VALUES (?, ?, ?, 1, ?, ?, ?)
        """, (invoice_id, item.get("service_id"), item["description"], price, price, item.get("source_price_id")))


def get_invoice_items(invoice_id):
    """Returns this invoice's snapshotted line items (description, price, source_price_id).
    Empty list if this invoice predates per-invoice item snapshots."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, service_id, description, line_total AS price, source_price_id "
        "FROM invoice_items WHERE invoice_id = ? ORDER BY id", (invoice_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_invoice_display_items(invoice):
    """Returns the line items to display/total for an invoice: its own snapshotted
    invoice_items if present, otherwise falls back to the client's current live
    service/price rows (legacy invoices created before per-invoice snapshots existed)."""
    items = get_invoice_items(invoice["id"])
    if items:
        return items
    return get_client_service_prices(invoice["client_id"])


def _recompute_and_store_totals(conn, invoice_id):
    """Recomputes subtotal_ht/tva_amount/total_ttc from this invoice's line items
    (or, for legacy invoices with no snapshot, the client's current prices) and
    writes them onto the invoice row. Called once whenever an invoice's items or
    tva_rate/business_type change, so compute_invoice_totals() can just read the
    stored columns afterwards instead of re-querying items on every call."""
    inv = conn.execute(
        "SELECT id, client_id, business_type, tva_rate FROM invoices WHERE id = ?", (invoice_id,)
    ).fetchone()
    if inv is None:
        return
    items = conn.execute(
        "SELECT line_total AS price FROM invoice_items WHERE invoice_id = ?", (invoice_id,)
    ).fetchall()
    if items:
        total_ttc = sum(r["price"] for r in items)
    else:
        rows = conn.execute(
            "SELECT price FROM client_service_prices WHERE client_id = ?", (inv["client_id"],)
        ).fetchall()
        total_ttc = sum(r["price"] for r in rows)

    business_type = inv["business_type"]
    tva_rate = inv["tva_rate"] if business_type == "company" else 0.0
    if business_type == "company" and tva_rate:
        subtotal_ht = total_ttc / (1 + tva_rate / 100.0)
        tva_amount = total_ttc - subtotal_ht
    else:
        subtotal_ht = total_ttc
        tva_amount = 0.0

    conn.execute(
        "UPDATE invoices SET subtotal_ht = ?, tva_amount = ?, total_ttc = ? WHERE id = ?",
        (subtotal_ht, tva_amount, total_ttc, invoice_id)
    )


def update_invoice(invoice_id, client_id, business_type, tva_rate, deadline, notes="", selected_items=None):
    """Updates an existing invoice's editable fields. The invoice number and creation
    date are never changed, to preserve the legally-required sequential numbering.
    selected_items, if given, replaces the invoice's snapshotted line items."""
    if business_type != "company":
        tva_rate = 0.0
    conn = get_connection()
    conn.execute("""
        UPDATE invoices SET client_id = ?, business_type = ?, tva_rate = ?, deadline = ?, notes = ?
        WHERE id = ?
    """, (client_id, business_type, tva_rate, deadline, notes, invoice_id))
    if selected_items is not None:
        _set_invoice_items(conn, invoice_id, selected_items)
    _recompute_and_store_totals(conn, invoice_id)
    conn.commit()
    conn.close()


def list_invoices(search: str = "", status: str = None, year: int = None, month: int = None, drafts_only: bool = False):
    """By default returns only finalized (numbered) invoices - drafts_only=True
    returns only drafts (numero IS NULL, shown in List SF), None returns both."""
    conn = get_connection()
    query = """
        SELECT invoices.*, clients.name as client_name
        FROM invoices JOIN clients ON invoices.client_id = clients.id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (invoices.numero LIKE ? OR clients.name LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if status:
        query += " AND invoices.status = ?"
        params.append(status)
    if year:
        query += " AND strftime('%Y', invoices.invoice_date) = ?"
        params.append(f"{year:04d}")
    if month:
        query += " AND strftime('%m', invoices.invoice_date) = ?"
        params.append(f"{month:02d}")
    if drafts_only is True:
        query += " AND invoices.numero IS NULL"
    elif drafts_only is False:
        query += " AND invoices.numero IS NOT NULL"
    query += " ORDER BY invoices.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_invoice_watchlisted(invoice_id, watchlisted: bool):
    # Deprecated: the star/watchlist system was replaced by draft (numero IS NULL)
    # vs. finalized invoices. Kept as a no-op only in case anything still calls it.
    pass



def get_invoice(invoice_id):
    conn = get_connection()
    inv = conn.execute("""
        SELECT invoices.*, clients.name as client_name, clients.address as client_address,
               clients.ice as client_ice, clients.phone as client_phone, clients.email as client_email
        FROM invoices JOIN clients ON invoices.client_id = clients.id
        WHERE invoices.id = ?
    """, (invoice_id,)).fetchone()
    if inv is None:
        conn.close()
        return None
    items = conn.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (invoice_id,)).fetchall()
    conn.close()
    result = dict(inv)
    result["items"] = [dict(i) for i in items]
    return result


def set_invoice_status(invoice_id, status):
    assert status in ("paid", "unpaid")
    conn = get_connection()
    conn.execute("UPDATE invoices SET status = ? WHERE id = ?", (status, invoice_id))
    conn.commit()
    conn.close()


def set_invoice_paid(invoice_id, payment_type, payment_date):
    conn = get_connection()
    conn.execute(
        "UPDATE invoices SET status = 'paid', payment_type = ?, payment_date = ? WHERE id = ?",
        (payment_type, payment_date, invoice_id)
    )
    conn.commit()
    conn.close()


def delete_invoice(invoice_id):
    """Deletes an invoice. If it was a finalized facture, the remaining factures of
    that year are resequenced afterwards so no permanent gap is left behind."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT numero, invoice_date FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        conn.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
        conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        if row is not None and row["numero"] is not None:
            year = int(row["invoice_date"].split("-")[0])
            _resequence_year(conn, year)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def unfinalize_invoice(invoice_id):
    """Reverts a finalized invoice back to draft (numero = NULL, status = 'unpaid').
    Its sequence_order slot is cleared too - a défactured invoice has no reserved
    spot at all while it sits in List SF, and gets a brand new slot at the end of
    the sequence whenever it's finalized again. The other invoices of that year
    are then resequenced to close the gap it leaves behind.
    Moves the invoice from Factures tab back to List SF tab."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT numero, invoice_date FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if row is None or row["numero"] is None:
            return
        year = int(row["invoice_date"].split("-")[0])
        conn.execute(
            "UPDATE invoices SET numero = NULL, sequence_order = NULL, status = 'unpaid' WHERE id = ?",
            (invoice_id,)
        )
        _resequence_year(conn, year)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- Credit / balances ----------------

def list_client_balances():
    """Returns per-client totals of unpaid invoices (outstanding credit/debt)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT clients.id as client_id, clients.name as client_name,
               COALESCE(SUM(CASE WHEN invoices.status = 'unpaid' AND invoices.numero IS NOT NULL THEN invoices.total_ttc ELSE 0 END), 0) as balance_due,
               COUNT(CASE WHEN invoices.status = 'unpaid' AND invoices.numero IS NOT NULL THEN 1 END) as unpaid_count
        FROM clients
        LEFT JOIN invoices ON invoices.client_id = clients.id
        GROUP BY clients.id
        HAVING balance_due > 0
        ORDER BY balance_due DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_clients_with_unpaid_invoices():
    """Returns clients that have at least one unpaid, finalized (numbered) invoice,
    along with the total "montant" - the sum of all their assigned services' prices."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT clients.id as client_id, clients.name as client_name,
               COUNT(CASE WHEN invoices.status = 'unpaid' AND invoices.numero IS NOT NULL THEN 1 END) as unpaid_count,
               (SELECT COALESCE(SUM(price), 0) FROM client_service_prices
                WHERE client_service_prices.client_id = clients.id) as montant
        FROM clients
        LEFT JOIN invoices ON invoices.client_id = clients.id
        GROUP BY clients.id
        HAVING unpaid_count > 0
        ORDER BY clients.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_unpaid_invoices_for_client(client_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM invoices WHERE client_id = ? AND status = 'unpaid' AND numero IS NOT NULL ORDER BY invoice_date",
        (client_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------- Dashboard stats ----------------

def count_clients():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    conn.close()
    return count


def count_invoices_by_status(status):
    assert status in ("paid", "unpaid")
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM invoices WHERE status = ? AND numero IS NOT NULL", (status,)).fetchone()[0]
    conn.close()
    return count


def compute_invoice_totals(invoice):
    """Given an invoice row (dict-like), returns (total_ttc, subtotal_ht, tva_amount).
    These are stored on the invoice row itself (kept up to date by
    _recompute_and_store_totals whenever items/tva_rate/business_type change), so this
    is now a plain read with no extra DB query - it used to re-fetch and re-sum this
    invoice's line items on every single call, which was the main source of the
    N+1-query slowdown in List SF, Factures, and the Editions/reports totals."""
    return invoice["total_ttc"], invoice["subtotal_ht"], invoice["tva_amount"]
