"""
Migration: Add universal approval columns to new modules.
Run this ONCE from the project root: python add_approval_columns.py

Tables affected:
  products, tool_receiving, tool_delivering, customers, vendors,
  salesmen, warehouses, product_categories, boms, manufacturing_orders,
  payment_methods, customer_groups, expense_categories
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')
# Fallback candidates in priority order
DB_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), 'instance', 'database.db'),
    os.path.join(os.path.dirname(__file__), 'instance', 'project_crm.db'),
    os.path.join(os.path.dirname(__file__), 'instance', 'crm.db'),
    os.path.join(os.path.dirname(__file__), 'instance', 'project.db'),
    os.path.join(os.path.dirname(__file__), 'project.db'),
]


TABLES = {
    'products': [
        ("is_approved", "BOOLEAN DEFAULT 1"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'tool_receiving': [
        ("is_approved", "BOOLEAN DEFAULT 0"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'tool_delivering': [
        ("is_approved", "BOOLEAN DEFAULT 0"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'customers': [
        ("is_approved", "BOOLEAN DEFAULT 1"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'vendors': [
        ("is_approved", "BOOLEAN DEFAULT 1"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'salesmen': [
        ("is_approved", "BOOLEAN DEFAULT 1"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'warehouses': [
        ("is_approved", "BOOLEAN DEFAULT 1"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'product_categories': [
        ("is_approved", "BOOLEAN DEFAULT 1"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'boms': [
        # Note: BOM already has `is_active` but not approval flags.
        # Using is_approved_flag to avoid conflict with is_active.
        ("is_approved_flag", "BOOLEAN DEFAULT 1"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'manufacturing_orders': [
        ("is_approved", "BOOLEAN DEFAULT 0"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'payment_methods': [
        ("is_approved", "BOOLEAN DEFAULT 1"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'customer_groups': [
        ("is_approved", "BOOLEAN DEFAULT 1"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
    ],
    'expense_categories': [
        ("is_approved", "BOOLEAN DEFAULT 1"),
        ("is_rejected", "BOOLEAN DEFAULT 0"),
        ("rejection_reason", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "DATETIME"),
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
        # Try candidates in priority order
        found = False
        for candidate in DB_CANDIDATES:
            if os.path.exists(candidate):
                DB_PATH = candidate
                found = True
                break
        if not found:
            print(f"ERROR: Database not found. Tried:")
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
