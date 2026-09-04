"""Creates the asset_categories table -- lets HR add asset categories
(Tools, Electronics, Vehicles, ...) on the fly from the Add/Edit Asset
form's "+ Add Category" quick-add, instead of typing a free-text category
by hand each time.

    CREATE TABLE asset_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(80) NOT NULL UNIQUE,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME
    );

Safe to run repeatedly: the table/index are only created if missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_hr_asset_categories.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

TABLE_DDL = """
    CREATE TABLE asset_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(80) NOT NULL UNIQUE,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME
    )
"""

INDEX_NAME = 'ix_asset_categories_name'
INDEX_DDL = 'CREATE INDEX ix_asset_categories_name ON asset_categories(name)'


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-hr-asset-categories-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'asset_categories' not in existing_tables:
        cur.execute(TABLE_DDL)
        print('  + table asset_categories created')
    else:
        print('  = table asset_categories already present — skipped')

    existing_indexes = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    if INDEX_NAME not in existing_indexes:
        cur.execute(INDEX_DDL)
        print(f'  + index {INDEX_NAME} created')
    else:
        print(f'  = index {INDEX_NAME} already present — skipped')

    # Seed from any distinct category strings already used on existing assets.
    existing_categories = {row[0] for row in cur.execute("SELECT name FROM asset_categories")}
    distinct_used = [row[0] for row in cur.execute(
        "SELECT DISTINCT category FROM assets WHERE category IS NOT NULL AND TRIM(category) != ''"
    )]
    for name in distinct_used:
        if name not in existing_categories:
            cur.execute("INSERT INTO asset_categories (name, is_active, created_at) VALUES (?, 1, ?)",
                        (name, datetime.utcnow().isoformat(sep=' ')))
            print(f'  + seeded category from existing asset data: {name}')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
