"""Add the "Add this to Invoice/Purchase Payment" link to Expenses.

Adds three columns to `expenses` (linked_sale_id, linked_bill_id,
is_payment_transfer) and one column to `bill_payments` (expense_id, mirroring
the existing payments.expense_id). Together these let an Expense apply its
amount as a real Payment/BillPayment against a Sale invoice or Purchase bill
instead of counting as a normal cost.

Safe to run repeatedly: each column is only added if missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_expense_payment_transfer.py
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

    backup = f'{DB_PATH}.bak-before-expense-payment-transfer-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    exp_columns = {row[1] for row in cur.execute('PRAGMA table_info(expenses)')}
    if 'linked_sale_id' not in exp_columns:
        cur.execute('ALTER TABLE expenses ADD COLUMN linked_sale_id INTEGER REFERENCES sales(id)')
        cur.execute('CREATE INDEX ix_expenses_linked_sale_id ON expenses (linked_sale_id)')
        print('  + expenses.linked_sale_id added')
    else:
        print('  = expenses.linked_sale_id already present — skipped')

    if 'linked_bill_id' not in exp_columns:
        cur.execute('ALTER TABLE expenses ADD COLUMN linked_bill_id INTEGER REFERENCES purchase_bills(id)')
        cur.execute('CREATE INDEX ix_expenses_linked_bill_id ON expenses (linked_bill_id)')
        print('  + expenses.linked_bill_id added')
    else:
        print('  = expenses.linked_bill_id already present — skipped')

    if 'is_payment_transfer' not in exp_columns:
        cur.execute('ALTER TABLE expenses ADD COLUMN is_payment_transfer BOOLEAN DEFAULT 0')
        cur.execute('CREATE INDEX ix_expenses_is_payment_transfer ON expenses (is_payment_transfer)')
        print('  + expenses.is_payment_transfer added')
    else:
        print('  = expenses.is_payment_transfer already present — skipped')

    bp_columns = {row[1] for row in cur.execute('PRAGMA table_info(bill_payments)')}
    if 'expense_id' not in bp_columns:
        cur.execute('ALTER TABLE bill_payments ADD COLUMN expense_id INTEGER REFERENCES expenses(id)')
        cur.execute('CREATE INDEX ix_bill_payments_expense_id ON bill_payments (expense_id)')
        print('  + bill_payments.expense_id added')
    else:
        print('  = bill_payments.expense_id already present — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
