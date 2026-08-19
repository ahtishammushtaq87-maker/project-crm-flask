"""Add the Packing Slip module permission columns to the `users` table.

Safe to run repeatedly: each column is added only if it is missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_packing_permissions.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

# (column, SQL type, default) — defaults mirror the model:
# view defaults ON so existing staff keep working like the other view flags,
# while add/edit/delete stay OFF until an admin grants them explicitly.
COLUMNS = [
    ('can_view_packing', 'BOOLEAN', '1'),
    ('can_add_packing', 'BOOLEAN', '0'),
    ('can_edit_packing', 'BOOLEAN', '0'),
    ('can_delete_packing', 'BOOLEAN', '0'),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-packing-perms-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = {row[1] for row in cur.execute('PRAGMA table_info(users)')}
    added = 0
    for name, sql_type, default in COLUMNS:
        if name in existing:
            print(f'  = {name} already present — skipped')
            continue
        cur.execute(
            f'ALTER TABLE users ADD COLUMN {name} {sql_type} DEFAULT {default}'
        )
        # ALTER TABLE ... DEFAULT already backfills existing rows in SQLite,
        # but be explicit so a NULL can never reach has_permission().
        cur.execute(f'UPDATE users SET {name} = {default} WHERE {name} IS NULL')
        print(f'  + {name} added (default {default})')
        added += 1

    conn.commit()
    conn.close()
    print(f'Done — {added} column(s) added.')


if __name__ == '__main__':
    main()
