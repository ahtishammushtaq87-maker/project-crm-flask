"""Add account/payment-method/bill-image columns to `fixed_expenses`.

Lets a Fixed Expense template optionally: charge its cycles against a
Journal Account (credit/money-out, applied to each posted cycle's Expense
row), carry a Payment Method, and carry a Bill Image — all copied onto every
Expense row the template generates. Existing rows get NULL for all three
(no account linked, no payment method, no image) — unchanged behavior.

Safe to run repeatedly: each column is added only if it is missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_fixed_expense_account_payment.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

# (column, SQL type, default)
COLUMNS = [
    ('account_id', 'INTEGER', 'NULL'),
    ('payment_method', 'VARCHAR(50)', 'NULL'),
    ('bill_image_path', 'VARCHAR(255)', 'NULL'),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-fixed-expense-account-payment-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = {row[1] for row in cur.execute('PRAGMA table_info(fixed_expenses)')}
    added = 0
    for name, sql_type, default in COLUMNS:
        if name in existing:
            print(f'  = {name} already present — skipped')
            continue
        cur.execute(f'ALTER TABLE fixed_expenses ADD COLUMN {name} {sql_type}')
        print(f'  + {name} added (default {default})')
        added += 1

    conn.commit()
    conn.close()
    print(f'Done — {added} column(s) added.')


if __name__ == '__main__':
    main()
