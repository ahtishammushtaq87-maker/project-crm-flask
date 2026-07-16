"""
Schema sync helper.

Compares the SQLAlchemy models (the source of truth in app/models.py) against an
actual SQLite database file and prints `ALTER TABLE ... ADD COLUMN ...` for every
column the models define but the database is missing.

Usage:
    # Just SHOW what's missing (safe, read-only) — run this on the VPS:
    python sync_schema.py instance/database.db

    # Actually APPLY the missing columns to that DB:
    python sync_schema.py instance/database.db --apply

Notes:
- SQLite `ADD COLUMN` is non-destructive: it never drops/rewrites data.
- It cannot add a column that is both NOT NULL and has no default; those are
  reported as a warning so you can handle them manually.
- Always back up first:  cp instance/database.db instance/database.db.bak
"""
import sys
import sqlite3

from sqlalchemy import inspect as sa_inspect

# Import the app so all models register on the metadata
from app import create_app, db
import app.models  # noqa: F401  (ensures every model class is imported)


def sqlite_type(col):
    """Best-effort SQLite column type for a SQLAlchemy column."""
    try:
        return col.type.compile(dialect=sqlite3_dialect)
    except Exception:
        # Fallback by python type
        pytype = getattr(col.type, 'python_type', str)
        return {int: 'INTEGER', float: 'REAL', bool: 'BOOLEAN'}.get(pytype, 'TEXT')


from sqlalchemy.dialects import sqlite as _sqlite
sqlite3_dialect = _sqlite.dialect()


def default_clause(col):
    """Render a DEFAULT clause matching the model's server/python default, if any."""
    d = col.default
    if d is None:
        return ''
    if getattr(d, 'is_scalar', False):
        val = d.arg
        if isinstance(val, bool):
            return f' DEFAULT {1 if val else 0}'
        if isinstance(val, (int, float)):
            return f' DEFAULT {val}'
        if isinstance(val, str):
            return f" DEFAULT '{val}'"
    return ''


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    db_path = sys.argv[1]
    apply = '--apply' in sys.argv[2:]

    app = create_app()
    with app.app_context():
        model_tables = db.metadata.tables  # name -> Table

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    existing_tables = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    statements = []
    warnings = []
    missing_tables = []

    for tname, table in model_tables.items():
        if tname not in existing_tables:
            missing_tables.append(tname)
            continue
        db_cols = {r[1] for r in cur.execute(f"PRAGMA table_info('{tname}')").fetchall()}
        for col in table.columns:
            if col.name in db_cols:
                continue
            coltype = sqlite_type(col)
            dflt = default_clause(col)
            if not col.nullable and not dflt:
                warnings.append(
                    f"-- SKIP {tname}.{col.name}: NOT NULL with no default — add manually."
                )
                continue
            statements.append(
                f"ALTER TABLE {tname} ADD COLUMN {col.name} {coltype}{dflt};"
            )

    print(f"\n=== Comparing models to: {db_path} ===")
    if missing_tables:
        print("\n-- Tables entirely missing (create via db.create_all(), not ALTER):")
        for t in missing_tables:
            print(f"--   {t}")
    if warnings:
        print("\n" + "\n".join(warnings))

    if not statements:
        print("\nNo missing columns. Database is in sync with the models. [OK]")
    else:
        print(f"\n-- {len(statements)} missing column(s):\n")
        for s in statements:
            print(s)
        if apply:
            for s in statements:
                cur.execute(s)
            conn.commit()
            print(f"\n[OK] Applied {len(statements)} column(s) to {db_path}.")
        else:
            print("\n(Run again with --apply to execute these against the DB.)")

    conn.close()


if __name__ == '__main__':
    main()
