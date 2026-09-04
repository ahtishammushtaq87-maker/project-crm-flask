"""Creates the tables for the new HR suite -- Leave & Absence,
Bonuses & Adjustments, Assets & Custody, and Final Settlements -- and adds
the two Attendance columns ('is_paid_leave', 'leave_request_id') used to
auto-mark a staff member Present/paid for the dates of an approved leave
request (see apply_leave_approval_to_attendance() in app/routes/hr.py).

New tables: leave_types, leave_requests, salary_adjustments, assets,
asset_assignments, settlements.

Safe to run repeatedly: every table/column is only created if missing, so
an already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_hr_leave_adjustments_assets_settlements.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

TABLES = {
    'leave_types': """
        CREATE TABLE leave_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(80) NOT NULL UNIQUE,
            is_paid BOOLEAN DEFAULT 1,
            default_annual_days FLOAT DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME
        )
    """,
    'leave_requests': """
        CREATE TABLE leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL REFERENCES staff(id),
            leave_type_id INTEGER NOT NULL REFERENCES leave_types(id),
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            days FLOAT DEFAULT 0,
            reason TEXT,
            evidence_path VARCHAR(255),
            status VARCHAR(20) DEFAULT 'pending',
            approved_by INTEGER REFERENCES users(id),
            approved_at DATETIME,
            rejection_reason TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at DATETIME
        )
    """,
    'salary_adjustments': """
        CREATE TABLE salary_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL REFERENCES staff(id),
            adjustment_type VARCHAR(20) NOT NULL,
            amount FLOAT NOT NULL,
            reason VARCHAR(255),
            is_recurring BOOLEAN DEFAULT 0,
            effective_from DATE,
            payroll_month INTEGER,
            payroll_year INTEGER,
            evidence_text VARCHAR(255),
            status VARCHAR(20) DEFAULT 'pending',
            approved_by INTEGER REFERENCES users(id),
            approved_at DATETIME,
            is_applied BOOLEAN DEFAULT 0,
            salary_payment_id INTEGER REFERENCES salary_payments(id),
            created_by INTEGER REFERENCES users(id),
            created_at DATETIME
        )
    """,
    'assets': """
        CREATE TABLE assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(150) NOT NULL,
            sku VARCHAR(80),
            serial_tag VARCHAR(120),
            category VARCHAR(80),
            purchase_date DATE,
            purchase_cost FLOAT DEFAULT 0,
            notes TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME
        )
    """,
    'asset_assignments': """
        CREATE TABLE asset_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL REFERENCES assets(id),
            staff_id INTEGER NOT NULL REFERENCES staff(id),
            issued_date DATE NOT NULL,
            condition_out VARCHAR(50),
            return_due_date DATE,
            returned_date DATE,
            condition_in VARCHAR(50),
            linked_voucher VARCHAR(120),
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at DATETIME
        )
    """,
    'settlements': """
        CREATE TABLE settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL REFERENCES staff(id),
            last_working_date DATE NOT NULL,
            initiated_at DATETIME,
            initiated_by INTEGER REFERENCES users(id),
            status VARCHAR(20) DEFAULT 'in_progress',
            last_day_approved BOOLEAN DEFAULT 0,
            attendance_locked BOOLEAN DEFAULT 0,
            funds_reconciled BOOLEAN DEFAULT 0,
            advance_confirmed BOOLEAN DEFAULT 0,
            exit_docs_signed BOOLEAN DEFAULT 0,
            salary_through_last_day FLOAT DEFAULT 0,
            leave_payout FLOAT DEFAULT 0,
            advance_recovery FLOAT DEFAULT 0,
            other_recovery FLOAT DEFAULT 0,
            net_settlement FLOAT DEFAULT 0,
            notes TEXT,
            cleared_by INTEGER REFERENCES users(id),
            cleared_at DATETIME,
            salary_payment_id INTEGER REFERENCES salary_payments(id),
            created_at DATETIME
        )
    """,
}

INDEXES = [
    ('ix_leave_requests_staff_id', 'CREATE INDEX ix_leave_requests_staff_id ON leave_requests(staff_id)'),
    ('ix_leave_requests_start_date', 'CREATE INDEX ix_leave_requests_start_date ON leave_requests(start_date)'),
    ('ix_leave_requests_status', 'CREATE INDEX ix_leave_requests_status ON leave_requests(status)'),
    ('ix_salary_adjustments_staff_id', 'CREATE INDEX ix_salary_adjustments_staff_id ON salary_adjustments(staff_id)'),
    ('ix_salary_adjustments_status', 'CREATE INDEX ix_salary_adjustments_status ON salary_adjustments(status)'),
    ('ix_assets_name', 'CREATE INDEX ix_assets_name ON assets(name)'),
    ('ix_asset_assignments_asset_id', 'CREATE INDEX ix_asset_assignments_asset_id ON asset_assignments(asset_id)'),
    ('ix_asset_assignments_staff_id', 'CREATE INDEX ix_asset_assignments_staff_id ON asset_assignments(staff_id)'),
    ('ix_settlements_staff_id', 'CREATE INDEX ix_settlements_staff_id ON settlements(staff_id)'),
    ('ix_settlements_status', 'CREATE INDEX ix_settlements_status ON settlements(status)'),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-hr-leave-adjustments-assets-settlements-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table_name, ddl in TABLES.items():
        if table_name not in existing_tables:
            cur.execute(ddl)
            print(f'  + table {table_name} created')
        else:
            print(f'  = table {table_name} already present — skipped')

    existing_indexes = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    for index_name, ddl in INDEXES:
        if index_name not in existing_indexes:
            cur.execute(ddl)
            print(f'  + index {index_name} created')
        else:
            print(f'  = index {index_name} already present — skipped')

    existing_attendance_columns = {row[1] for row in cur.execute('PRAGMA table_info(attendance)')}
    if 'is_paid_leave' not in existing_attendance_columns:
        cur.execute('ALTER TABLE attendance ADD COLUMN is_paid_leave BOOLEAN DEFAULT 0')
        print('  + is_paid_leave column added to attendance')
    else:
        print('  = is_paid_leave column already present on attendance — skipped')

    if 'leave_request_id' not in existing_attendance_columns:
        cur.execute('ALTER TABLE attendance ADD COLUMN leave_request_id INTEGER REFERENCES leave_requests(id)')
        print('  + leave_request_id column added to attendance')
    else:
        print('  = leave_request_id column already present on attendance — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
