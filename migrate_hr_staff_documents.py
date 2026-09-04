"""Creates the staff_documents table -- lets HR attach any number of named
documents to a staff member (Passport, Medical Certificate, Reference
Letter, ...) beyond the 3 fixed CNIC/CV/Agreement Letter fields already on
`staff`, uploaded one or many at a time from the Add/Edit Staff form.

    CREATE TABLE staff_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL REFERENCES staff(id),
        name VARCHAR(150) NOT NULL,
        file_path VARCHAR(255) NOT NULL,
        uploaded_by INTEGER REFERENCES users(id),
        created_at DATETIME
    );

Safe to run repeatedly: the table/index are only created if missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_hr_staff_documents.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

TABLE_DDL = """
    CREATE TABLE staff_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL REFERENCES staff(id),
        name VARCHAR(150) NOT NULL,
        file_path VARCHAR(255) NOT NULL,
        uploaded_by INTEGER REFERENCES users(id),
        created_at DATETIME
    )
"""

INDEX_NAME = 'ix_staff_documents_staff_id'
INDEX_DDL = 'CREATE INDEX ix_staff_documents_staff_id ON staff_documents(staff_id)'


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-hr-staff-documents-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'staff_documents' not in existing_tables:
        cur.execute(TABLE_DDL)
        print('  + table staff_documents created')
    else:
        print('  = table staff_documents already present — skipped')

    existing_indexes = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    if INDEX_NAME not in existing_indexes:
        cur.execute(INDEX_DDL)
        print(f'  + index {INDEX_NAME} created')
    else:
        print(f'  = index {INDEX_NAME} already present — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
