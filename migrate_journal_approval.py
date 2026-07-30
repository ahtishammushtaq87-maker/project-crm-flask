"""
Migration: Add approval columns to journal_entries table.
Sets existing entries to is_approved = 1 so existing accounting data is preserved.
"""
import sqlite3, os, glob

COLUMNS = [
    ("is_approved", "BOOLEAN DEFAULT 1"),
    ("is_rejected", "BOOLEAN DEFAULT 0"),
    ("rejection_reason", "TEXT"),
    ("approved_by", "INTEGER"),
    ("approved_at", "DATETIME"),
]

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None

def run():
    db_files = glob.glob(os.path.join(os.path.dirname(__file__), '**', '*.db'), recursive=True)
    if not db_files:
        print("ERROR: No database file found.")
        return

    for db_path in db_files:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if not table_exists(cursor, 'journal_entries'):
            conn.close()
            continue

        print(f"Migrating table 'journal_entries' in: {db_path}")
        added = 0
        for col_name, col_def in COLUMNS:
            if not column_exists(cursor, 'journal_entries', col_name):
                try:
                    cursor.execute(f"ALTER TABLE journal_entries ADD COLUMN {col_name} {col_def}")
                    print(f"  [+] Added column: journal_entries.{col_name}")
                    added += 1
                except Exception as e:
                    print(f"  [ERR] Failed adding {col_name}: {e}")
            else:
                print(f"  [=] Column journal_entries.{col_name} already exists.")

        # Ensure existing records have is_approved = 1 and is_rejected = 0 if NULL
        cursor.execute("UPDATE journal_entries SET is_approved = 1 WHERE is_approved IS NULL")
        cursor.execute("UPDATE journal_entries SET is_rejected = 0 WHERE is_rejected IS NULL")

        conn.commit()
        conn.close()
        print(f"Migration complete for {db_path}: {added} columns added.\n")

if __name__ == '__main__':
    run()
