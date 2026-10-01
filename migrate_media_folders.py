"""Folders for the Media Library.

    CREATE TABLE media_folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(150) NOT NULL,
        parent_id INTEGER REFERENCES media_folders(id),
        created_by_id INTEGER REFERENCES users(id),
        created_at DATETIME
    );
    CREATE INDEX ix_media_folders_parent_id ON media_folders(parent_id);
    ALTER TABLE media ADD COLUMN folder_id INTEGER REFERENCES media_folders(id);
    CREATE INDEX ix_media_folder_id ON media(folder_id);

Existing files keep folder_id = NULL, i.e. they stay at the top level of the
Media Library. Files on disk are never moved - folders are only an
organisation layer in the database.

Safe to run repeatedly. A timestamped backup of the SQLite file is taken
first. (The app also creates these on startup.)

    python migrate_media_folders.py
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

    backup = f'{DB_PATH}.bak-before-media-folders-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS media_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(150) NOT NULL,
            parent_id INTEGER REFERENCES media_folders(id),
            created_by_id INTEGER REFERENCES users(id),
            created_at DATETIME
        )
    """)
    cur.execute('CREATE INDEX IF NOT EXISTS ix_media_folders_parent_id ON media_folders(parent_id)')
    print('  = media_folders table ready')

    cols = {row[1] for row in cur.execute('PRAGMA table_info(media)')}
    if 'folder_id' in cols:
        print('  = media.folder_id already present — skipped')
    else:
        cur.execute('ALTER TABLE media ADD COLUMN folder_id INTEGER REFERENCES media_folders(id)')
        print('  + media.folder_id added')
    cur.execute('CREATE INDEX IF NOT EXISTS ix_media_folder_id ON media(folder_id)')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
