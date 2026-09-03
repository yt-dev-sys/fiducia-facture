"""Explicit, transactional SQLite schema migrations."""
from __future__ import annotations

import sqlite3

CURRENT_SCHEMA_VERSION = 1


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
