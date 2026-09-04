"""Creates the salary_revisions table -- a permanent record of every
Staff.monthly_salary change (previous amount, new amount, effective date,
reason), so salary increases/decreases are never lost the way a plain
column overwrite would lose them.

    CREATE TABLE salary_revisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL REFERENCES staff(id),
        previous_salary FLOAT NOT NULL,
        new_salary FLOAT NOT NULL,
        effective_from DATE NOT NULL,
        reason VARCHAR(255),
        approved_by INTEGER REFERENCES users(id),
        created_by INTEGER REFERENCES users(id),
        created_at DATETIME
    );

Safe to run repeatedly: the table/indexes are only created if missing, so
an already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_hr_salary_revisions.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

TABLE_DDL = """
    CREATE TABLE salary_revisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL REFERENCES staff(id),
        previous_salary FLOAT NOT NULL,
        new_salary FLOAT NOT NULL,
        effective_from DATE NOT NULL,
        reason VARCHAR(255),
        approved_by INTEGER REFERENCES users(id),
        created_by INTEGER REFERENCES users(id),
        created_at DATETIME
    )
"""

INDEXES = [
    ('ix_salary_revisions_staff_id', 'CREATE INDEX ix_salary_revisions_staff_id ON salary_revisions(staff_id)'),
    ('ix_salary_revisions_effective_from', 'CREATE INDEX ix_salary_revisions_effective_from ON salary_revisions(effective_from)'),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-hr-salary-revisions-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'salary_revisions' not in existing_tables:
        cur.execute(TABLE_DDL)
        print('  + table salary_revisions created')
    else:
        print('  = table salary_revisions already present — skipped')

    existing_indexes = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    for index_name, ddl in INDEXES:
        if index_name not in existing_indexes:
            cur.execute(ddl)
            print(f'  + index {index_name} created')
        else:
            print(f'  = index {index_name} already present — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
