"""Explicit, transactional SQLite schema migrations."""
from __future__ import annotations

import sqlite3

CURRENT_SCHEMA_VERSION = 4


def _ensure_schema_table(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version(version) VALUES (0)")


def get_schema_version(conn: sqlite3.Connection) -> int:
    _ensure_schema_table(conn)
    return int(conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()[0])


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("UPDATE schema_version SET version = ?", (version,))


def migrate(conn: sqlite3.Connection) -> int:
    """Run migrations one version at a time. Caller must have created a backup."""
    version = get_schema_version(conn)
    if version > CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Base de données plus récente ({version}) que cette version de Fiducia Facture "
            f"({CURRENT_SCHEMA_VERSION})."
        )

    # Version 1 represents the schema that the current application creates.
    # Existing databases are adopted only after their legacy compatibility work
    # has completed in database.init_db(). Future migrations must be added as
    # v2, v3, ... and never modify the user's data outside a transaction.
    while version < CURRENT_SCHEMA_VERSION:
        next_version = version + 1
        conn.execute("SAVEPOINT fiducia_migration")
        try:
            if next_version == 1:
                pass
            elif next_version == 2:
                # Give every invoice a permanent "sequence_order" slot, separate from its
                # displayed numero. numero is renumbered on the fly (see database._resequence_year)
                # so the Factures tab always shows a gapless 001, 002, 003... but sequence_order
                # never changes once assigned, so an invoice that is défacturé and later
                # re-facturé returns to the same relative position instead of jumping to the end.
                existing_cols = [r["name"] for r in conn.execute("PRAGMA table_info(invoices)").fetchall()]
                if "sequence_order" not in existing_cols:
                    conn.execute("ALTER TABLE invoices ADD COLUMN sequence_order INTEGER")

                # Backfill: every invoice that already has a number (numero if finalized,
                # reserved_numero if it's a défactured draft waiting to be re-facturé) gets
                # its slot from that number, so existing data keeps its relative order.
                rows = conn.execute(
                    "SELECT id, numero, reserved_numero FROM invoices WHERE sequence_order IS NULL"
                ).fetchall()
                for row in rows:
                    source = row["numero"] or row["reserved_numero"]
                    if not source:
                        continue
                    try:
                        seq = int(str(source).split("-")[0])
                    except (ValueError, AttributeError):
                        continue
                    conn.execute("UPDATE invoices SET sequence_order = ? WHERE id = ?", (seq, row["id"]))
            elif next_version == 3:
                # Store each invoice's totals on the row itself instead of recomputing them
                # from invoice_items (or the client's live prices) on every single read.
                # compute_invoice_totals() now just reads these columns.
                invoices = conn.execute(
                    "SELECT id, client_id, business_type, tva_rate FROM invoices"
                ).fetchall()
                for inv in invoices:
                    items = conn.execute(
                        "SELECT line_total AS price FROM invoice_items WHERE invoice_id = ?", (inv["id"],)
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
                        (subtotal_ht, tva_amount, total_ttc, inv["id"])
                    )
            elif next_version == 4:
                # Défactured drafts no longer keep a reserved sequence_order slot -
                # re-facturing now always assigns a fresh one at the end of the
                # sequence. Clear out any slot left over from before this change on
                # invoices that are currently drafts (numero IS NULL).
                conn.execute(
                    "UPDATE invoices SET sequence_order = NULL WHERE numero IS NULL AND sequence_order IS NOT NULL"
                )
            else:
                raise RuntimeError(f"Migration non implémentée : v{version} → v{next_version}")
            set_schema_version(conn, next_version)
            conn.execute("RELEASE SAVEPOINT fiducia_migration")
            version = next_version
        except Exception:
            conn.execute("ROLLBACK TO SAVEPOINT fiducia_migration")
            conn.execute("RELEASE SAVEPOINT fiducia_migration")
            raise
    return version
