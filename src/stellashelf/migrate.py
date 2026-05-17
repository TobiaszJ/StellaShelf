"""Schema migration runner for StellaShelf.

Migrations live in db_migrations/versions/ as vXXX_desc.py files.
Each must expose an upgrade(conn) function receiving a SQLAlchemy connection.
The db_migrations/ directory is gitignored — it only exists locally.

Version tracking via _schema_version table in the database.
"""

import importlib.util
import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "db_migrations" / "versions"


def _ensure_version_table(conn):
    from sqlalchemy import text

    conn.execute(text("CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER NOT NULL)"))
    if conn.execute(text("SELECT COUNT(*) FROM _schema_version")).scalar() == 0:
        conn.execute(text("INSERT INTO _schema_version (version) VALUES (0)"))
    conn.commit()


def _current_version(conn) -> int:
    from sqlalchemy import text

    return conn.execute(text("SELECT version FROM _schema_version LIMIT 1")).scalar() or 0


def _set_version(conn, version: int):
    from sqlalchemy import text

    conn.execute(text("UPDATE _schema_version SET version = :v"), {"v": version})
    conn.commit()


def _discover_migrations() -> list[tuple[int, Path]]:
    if not MIGRATIONS_DIR.exists():
        return []
    migrations = []
    for fp in sorted(MIGRATIONS_DIR.glob("v*.py")):
        m = re.match(r"v(\d+)", fp.stem)
        if m:
            migrations.append((int(m.group(1)), fp))
    return migrations


def run_migrations(engine):
    with engine.connect() as conn:
        _ensure_version_table(conn)
        current = _current_version(conn)

    migrations = _discover_migrations()
    if not migrations:
        return current

    for ver, fp in migrations:
        if ver <= current:
            continue

        spec = importlib.util.spec_from_file_location(fp.stem, str(fp))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with engine.connect() as conn:
            mod.upgrade(conn)
            _set_version(conn, ver)

    with engine.connect() as conn:
        return _current_version(conn)
