"""Adds the umbrella HR-suite permission columns to `users`:
can_view_hr, can_add_hr, can_edit_hr, can_delete_hr.

These gate the newer HR module (Leave & Absence, Bonuses & Adjustments,
Assets & Custody, Final Settlements, Company Funds summary -- see
app/routes/hr.py). Staff/Attendance/Payroll/Advances keep using the
existing can_*_salary / can_*_attendance columns unchanged.

Kept as a separate script from migrate_hr_leave_adjustments_assets_settlements.py
so permission rollout can be re-run independently (e.g. on a database where
the HR tables already exist via db.create_all() but this column is missing).

Safe to run repeatedly: each column is only added if missing. A timestamped
backup of the SQLite file is taken first.

    python migrate_hr_permissions.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

COLUMNS = [
    ('can_view_hr', 'ALTER TABLE users ADD COLUMN can_view_hr BOOLEAN DEFAULT 1'),
    ('can_add_hr', 'ALTER TABLE users ADD COLUMN can_add_hr BOOLEAN DEFAULT 0'),
    ('can_edit_hr', 'ALTER TABLE users ADD COLUMN can_edit_hr BOOLEAN DEFAULT 0'),
    ('can_delete_hr', 'ALTER TABLE users ADD COLUMN can_delete_hr BOOLEAN DEFAULT 0'),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-hr-permissions-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_columns = {row[1] for row in cur.execute('PRAGMA table_info(users)')}
    for column_name, ddl in COLUMNS:
        if column_name not in existing_columns:
            cur.execute(ddl)
            print(f'  + {column_name} column added to users')
        else:
            print(f'  = {column_name} column already present — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
