"""Add the calendar-month cycle columns to the `fixed_expenses` table.

Lets a Fixed Expense reset on the 1st of each month (28-31 days, matching the
real calendar) instead of only a fixed N-day rolling cycle. Existing rows are
left on 'fixed_days' (their current behavior, unchanged) — the new mode is
opt-in per template via Edit.

Safe to run repeatedly: each column is added only if it is missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_fixed_expense_cycle_type.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

# (column, SQL type, default)
COLUMNS = [
    ('cycle_type', 'VARCHAR(20)', "'fixed_days'"),
    ('cycle_base_n', 'INTEGER', '0'),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-fixed-expense-cycle-type-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
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
        cur.execute(
            f'ALTER TABLE fixed_expenses ADD COLUMN {name} {sql_type} DEFAULT {default}'
        )
        cur.execute(f'UPDATE fixed_expenses SET {name} = {default} WHERE {name} IS NULL')
        print(f'  + {name} added (default {default})')
        added += 1

    conn.commit()
    conn.close()
    print(f'Done — {added} column(s) added.')


if __name__ == '__main__':
    main()
