"""
Add `needs_approval` to payments and customer_advances.

Why: staff-recorded payments/advances now apply to the invoice immediately
(is_approved=True) while still raising an admin approval request. The review
state therefore needs its own flag, separate from `is_approved`, which stays
the money flag ("this amount is already in Sale.paid_amount").

Backfill is deliberately FALSE for every existing row: rows that are currently
pending (is_approved=False) have NOT had their money applied, so they must keep
flowing through the original "approve to apply" path. Only newly created
records use the immediate-apply behaviour.

Safe to run more than once — it checks for the column first and makes no
changes if it is already present.
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def table_exists(cur, table):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def migrate(db_path):
    if not os.path.exists(db_path):
        print(f"  Database not found: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    changed = False

    for table in ('payments', 'customer_advances'):
        if not table_exists(cur, table):
            print(f"  [skip] table '{table}' does not exist")
            continue
        if column_exists(cur, table, 'needs_approval'):
            print(f"  [ok]   {table}.needs_approval already present")
            continue
        cur.execute(
            f"ALTER TABLE {table} ADD COLUMN needs_approval BOOLEAN DEFAULT 0"
        )
        cur.execute(f"UPDATE {table} SET needs_approval = 0 WHERE needs_approval IS NULL")
        cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_needs_approval ON {table} (needs_approval)")
        print(f"  [added] {table}.needs_approval (backfilled to 0 for all existing rows)")
        changed = True

    conn.commit()

    # Report what the admin queue will look like after migration
    if table_exists(cur, 'payments'):
        cur.execute("SELECT COUNT(*) FROM payments WHERE is_approved = 0 AND is_rejected = 0")
        print(f"  legacy pending payments (still 'approve to apply'): {cur.fetchone()[0]}")
    conn.close()
    return changed


if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'instance', 'database.db')
    print(f"Migrating: {db_path}")
    migrate(db_path)
    print("Done.")
