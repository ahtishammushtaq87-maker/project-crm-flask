"""Add a `notes` column to `sale_returns` — the optional note field now shown
under "Reason for Return" on the Sales Return create form.

Safe to run repeatedly: the column is only added if missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_sale_return_notes.py
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

    backup = f'{DB_PATH}.bak-before-sale-return-notes-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    columns = {row[1] for row in cur.execute('PRAGMA table_info(sale_returns)')}
    if 'notes' not in columns:
        cur.execute('ALTER TABLE sale_returns ADD COLUMN notes TEXT')
        print('  + sale_returns.notes added')
    else:
        print('  = sale_returns.notes already present — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
