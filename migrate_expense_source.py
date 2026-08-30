"""Add the `expense_sources` table and `source_id` column on
`expense_account_transactions`.

Source is a reference tag for where the money in a debit ("Add Money")
transaction came from (e.g. Owner Investment, Bank Loan, Sales Collection) —
purely descriptive, used for filtering, same idea as ExpenseCategory but for
debit entries. Existing rows get NULL (no source) — unchanged behavior.

Safe to run repeatedly: the table/column are only created if missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_expense_source.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-expense-source-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'expense_sources' not in tables:
        cur.execute('''
            CREATE TABLE expense_sources (
                id INTEGER PRIMARY KEY,
                name VARCHAR(120) NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME,
                created_by INTEGER,
                FOREIGN KEY(created_by) REFERENCES users(id)
            )
        ''')
        print('  + expense_sources table created')
    else:
        print('  = expense_sources table already present — skipped')

    existing_columns = {row[1] for row in cur.execute('PRAGMA table_info(expense_account_transactions)')}
    if 'source_id' not in existing_columns:
        cur.execute('ALTER TABLE expense_account_transactions ADD COLUMN source_id INTEGER REFERENCES expense_sources(id)')
        print('  + source_id column added to expense_account_transactions')
    else:
        print('  = source_id column already present — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
