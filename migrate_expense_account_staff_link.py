"""Add `staff_id` to `expense_accounts` — links an Expense account back to
the HR Staff member it was auto-created for (see
_ensure_staff_expense_account in app/routes/salary.py). One account per
staff member, enforced by a unique index (NULLs are exempt, so accounts not
tied to any staff member are unaffected). Existing rows get NULL — unchanged
behavior.

Safe to run repeatedly: the column/index are only created if missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_expense_account_staff_link.py
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

    backup = f'{DB_PATH}.bak-before-expense-account-staff-link-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_columns = {row[1] for row in cur.execute('PRAGMA table_info(expense_accounts)')}
    if 'staff_id' not in existing_columns:
        cur.execute('ALTER TABLE expense_accounts ADD COLUMN staff_id INTEGER REFERENCES staff(id)')
        print('  + staff_id column added to expense_accounts')
    else:
        print('  = staff_id column already present — skipped')

    existing_indexes = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    if 'ux_expense_accounts_staff_id' not in existing_indexes:
        cur.execute('CREATE UNIQUE INDEX ux_expense_accounts_staff_id ON expense_accounts(staff_id)')
        print('  + unique index ux_expense_accounts_staff_id created')
    else:
        print('  = unique index ux_expense_accounts_staff_id already present — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
