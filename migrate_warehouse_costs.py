"""Per-warehouse item cost + shipping price / image on Warehouse Transfers.

    ALTER TABLE product_warehouse_stock  ADD COLUMN cost_price FLOAT;
    ALTER TABLE warehouse_transfers      ADD COLUMN shipping_cost FLOAT DEFAULT 0;
    ALTER TABLE warehouse_transfers      ADD COLUMN image_path VARCHAR(255);
    ALTER TABLE warehouse_transfer_items ADD COLUMN unit_cost FLOAT;
    ALTER TABLE warehouse_transfer_items ADD COLUMN shipping_share FLOAT DEFAULT 0;

product_warehouse_stock.cost_price stays NULL for every existing row, which
means "use the item's normal cost" - so nothing changes for existing data
until a transfer with shipping, a manufacturing order or a manual edit gives
a warehouse its own cost. Existing transfer lines keep unit_cost NULL
(reversing them only moves quantity back, exactly as before).

Safe to run repeatedly: columns are only added if missing. A timestamped
backup of the SQLite file is taken first. (The app also adds these columns
on startup.)

    python migrate_warehouse_costs.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

COLUMNS = [
    ('product_warehouse_stock', 'cost_price', 'FLOAT'),
    ('warehouse_transfers', 'shipping_cost', 'FLOAT DEFAULT 0'),
    ('warehouse_transfers', 'image_path', 'VARCHAR(255)'),
    ('warehouse_transfer_items', 'unit_cost', 'FLOAT'),
    ('warehouse_transfer_items', 'shipping_share', 'FLOAT DEFAULT 0'),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-warehouse-costs-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, col, ddl in COLUMNS:
        if table not in tables:
            print(f'  ! table {table} missing — run migrate_warehouse_transfers.py first')
            continue
        existing = {row[1] for row in cur.execute(f'PRAGMA table_info({table})')}
        if col in existing:
            print(f'  = {table}.{col} already present — skipped')
            continue
        cur.execute(f'ALTER TABLE {table} ADD COLUMN {col} {ddl}')
        print(f'  + {table}.{col} added')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
