"""
Migration: Add action-approval columns to purchase_bills.

These support the "Cancel Remaining / Reverse Cancellation needs admin approval"
workflow on the purchase bill details page. When a non-admin requests one of
those actions it is held on the bill until an admin approves it.

Run this ONCE from the project root:  python add_bill_cancel_approval_columns.py

Columns added to purchase_bills:
  pending_action           TEXT      -- 'cancel' | 'reverse' | NULL
  pending_action_reason    TEXT      -- optional reason from requester
  pending_action_payload   TEXT      -- JSON {purchase_item_id: cancel_qty}
  pending_action_by        INTEGER   -- requesting user id
  pending_action_at        DATETIME  -- when requested
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')
DB_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), 'instance', 'database.db'),
    os.path.join(os.path.dirname(__file__), 'instance', 'project_crm.db'),
    os.path.join(os.path.dirname(__file__), 'instance', 'crm.db'),
    os.path.join(os.path.dirname(__file__), 'instance', 'project.db'),
    os.path.join(os.path.dirname(__file__), 'project.db'),
]

TABLES = {
    'purchase_bills': [
        ("pending_action", "TEXT"),
        ("pending_action_reason", "TEXT"),
        ("pending_action_payload", "TEXT"),
        ("pending_action_by", "INTEGER"),
        ("pending_action_at", "DATETIME"),
    ],
}


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def run():
    global DB_PATH
    if not os.path.exists(DB_PATH):
        found = False
        for candidate in DB_CANDIDATES:
            if os.path.exists(candidate):
                DB_PATH = candidate
                found = True
                break
        if not found:
            print("ERROR: Database not found. Tried:")
            for c in DB_CANDIDATES:
                print(f"  {c}")
            return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    added = 0
    skipped = 0

    for table, columns in TABLES.items():
        if not table_exists(cursor, table):
            print(f"  [SKIP] Table '{table}' not found — skipping.")
            continue
        for col_name, col_def in columns:
            if column_exists(cursor, table, col_name):
                skipped += 1
            else:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    print(f"  [+] {table}.{col_name}")
                    added += 1
                except Exception as e:
                    print(f"  [ERR] {table}.{col_name}: {e}")

    conn.commit()
    conn.close()
    print(f"\nMigration complete: {added} columns added, {skipped} already existed.")


if __name__ == '__main__':
    run()
