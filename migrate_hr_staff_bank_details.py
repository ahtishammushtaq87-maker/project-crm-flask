"""Adds a Cash/Bank payment method to `staff`, plus the bank detail fields
that apply only when Bank is selected:

    ALTER TABLE staff ADD COLUMN payment_method VARCHAR(10) DEFAULT 'cash';
    ALTER TABLE staff ADD COLUMN bank_name VARCHAR(150);
    ALTER TABLE staff ADD COLUMN bank_account_title VARCHAR(150);
    ALTER TABLE staff ADD COLUMN bank_account_number VARCHAR(50);
    ALTER TABLE staff ADD COLUMN bank_branch VARCHAR(150);

Existing staff default to 'cash' with no bank details -- unchanged behavior.

Safe to run repeatedly: each column is only added if missing. A timestamped
backup of the SQLite file is taken first.

    python migrate_hr_staff_bank_details.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

COLUMNS = [
    ('payment_method', "ALTER TABLE staff ADD COLUMN payment_method VARCHAR(10) DEFAULT 'cash'"),
    ('bank_name', 'ALTER TABLE staff ADD COLUMN bank_name VARCHAR(150)'),
    ('bank_account_title', 'ALTER TABLE staff ADD COLUMN bank_account_title VARCHAR(150)'),
    ('bank_account_number', 'ALTER TABLE staff ADD COLUMN bank_account_number VARCHAR(50)'),
    ('bank_branch', 'ALTER TABLE staff ADD COLUMN bank_branch VARCHAR(150)'),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-hr-staff-bank-details-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_columns = {row[1] for row in cur.execute('PRAGMA table_info(staff)')}
    for column_name, ddl in COLUMNS:
        if column_name not in existing_columns:
            cur.execute(ddl)
            print(f'  + {column_name} column added to staff')
        else:
            print(f'  = {column_name} column already present — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
