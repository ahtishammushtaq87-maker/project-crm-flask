"""Create the Expense module's OWN independent account system.

Adds two new tables — `expense_accounts` and `expense_account_transactions`
— and a new `expense_account_id` column on `fixed_expenses`. This replaces
the earlier design where Expense borrowed the Journal module's accounts
(journal_accounts/journal_entries/journal_lines): Expense now owns its
accounts end to end, fully independent of Journal. The old
`fixed_expenses.account_id` (-> journal_accounts) column is left in place,
untouched, purely so any pre-existing linked data keeps reading back
correctly — nothing writes to it anymore.

Safe to run repeatedly: each table/column is only created if missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_expense_own_accounts.py
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

    backup = f'{DB_PATH}.bak-before-expense-own-accounts-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_tables = {row[0] for row in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}

    if 'expense_accounts' not in existing_tables:
        cur.execute('''
            CREATE TABLE expense_accounts (
                id INTEGER PRIMARY KEY,
                name VARCHAR(120) NOT NULL UNIQUE,
                account_type VARCHAR(50),
                opening_balance FLOAT DEFAULT 0,
                notes TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME,
                created_by INTEGER REFERENCES users(id)
            )
        ''')
        cur.execute('CREATE INDEX ix_expense_accounts_name ON expense_accounts (name)')
        print('  + created table expense_accounts')
    else:
        print('  = expense_accounts already present — skipped')

    if 'expense_account_transactions' not in existing_tables:
        cur.execute('''
            CREATE TABLE expense_account_transactions (
                id INTEGER PRIMARY KEY,
                account_id INTEGER NOT NULL REFERENCES expense_accounts(id),
                expense_id INTEGER REFERENCES expenses(id),
                date DATE NOT NULL,
                entry_type VARCHAR(10) NOT NULL DEFAULT 'credit',
                amount FLOAT NOT NULL DEFAULT 0,
                description TEXT,
                reference VARCHAR(120),
                bill_image_path VARCHAR(255),
                is_approved BOOLEAN DEFAULT 0,
                is_rejected BOOLEAN DEFAULT 0,
                rejection_reason TEXT,
                approved_by INTEGER REFERENCES users(id),
                approved_at DATETIME,
                created_by INTEGER REFERENCES users(id),
                created_at DATETIME
            )
        ''')
        cur.execute('CREATE INDEX ix_expense_account_transactions_account_id ON expense_account_transactions (account_id)')
        cur.execute('CREATE INDEX ix_expense_account_transactions_expense_id ON expense_account_transactions (expense_id)')
        cur.execute('CREATE INDEX ix_expense_account_transactions_date ON expense_account_transactions (date)')
        cur.execute('CREATE INDEX ix_expense_account_transactions_is_approved ON expense_account_transactions (is_approved)')
        cur.execute('CREATE INDEX ix_expense_account_transactions_is_rejected ON expense_account_transactions (is_rejected)')
        print('  + created table expense_account_transactions')
    else:
        print('  = expense_account_transactions already present — skipped')

    fx_columns = {row[1] for row in cur.execute('PRAGMA table_info(fixed_expenses)')}
    if 'expense_account_id' not in fx_columns:
        cur.execute('ALTER TABLE fixed_expenses ADD COLUMN expense_account_id INTEGER REFERENCES expense_accounts(id)')
        print('  + fixed_expenses.expense_account_id added')
    else:
        print('  = fixed_expenses.expense_account_id already present — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
