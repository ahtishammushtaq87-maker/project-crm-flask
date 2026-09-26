"""Creates the warehouse_transfers / warehouse_transfer_items tables for the
Inventory > Warehouse Transfers module (move item quantity from one
warehouse to another; edit/delete reverses the stock movement).

    CREATE TABLE warehouse_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transfer_number VARCHAR(50) NOT NULL UNIQUE,
        date DATE NOT NULL,
        from_warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
        to_warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
        reference VARCHAR(100),
        notes TEXT,
        created_by INTEGER REFERENCES users(id),
        updated_by INTEGER REFERENCES users(id),
        created_at DATETIME,
        updated_at DATETIME
    );
    CREATE TABLE warehouse_transfer_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transfer_id INTEGER NOT NULL REFERENCES warehouse_transfers(id),
        product_id INTEGER NOT NULL REFERENCES products(id),
        quantity FLOAT NOT NULL DEFAULT 0
    );

Safe to run repeatedly: tables/indexes are only created if missing. A
timestamped backup of the SQLite file is taken first.

    python migrate_warehouse_transfers.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

TABLES = {
    'warehouse_transfers': """
        CREATE TABLE warehouse_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_number VARCHAR(50) NOT NULL UNIQUE,
            date DATE NOT NULL,
            from_warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
            to_warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
            reference VARCHAR(100),
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            updated_by INTEGER REFERENCES users(id),
            created_at DATETIME,
            updated_at DATETIME
        )
    """,
    'warehouse_transfer_items': """
        CREATE TABLE warehouse_transfer_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_id INTEGER NOT NULL REFERENCES warehouse_transfers(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity FLOAT NOT NULL DEFAULT 0
        )
    """,
}

INDEXES = {
    'ix_warehouse_transfers_transfer_number': 'CREATE UNIQUE INDEX ix_warehouse_transfers_transfer_number ON warehouse_transfers(transfer_number)',
    'ix_warehouse_transfers_from_warehouse_id': 'CREATE INDEX ix_warehouse_transfers_from_warehouse_id ON warehouse_transfers(from_warehouse_id)',
    'ix_warehouse_transfers_to_warehouse_id': 'CREATE INDEX ix_warehouse_transfers_to_warehouse_id ON warehouse_transfers(to_warehouse_id)',
    'ix_warehouse_transfer_items_transfer_id': 'CREATE INDEX ix_warehouse_transfer_items_transfer_id ON warehouse_transfer_items(transfer_id)',
    'ix_warehouse_transfer_items_product_id': 'CREATE INDEX ix_warehouse_transfer_items_product_id ON warehouse_transfer_items(product_id)',
}


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-warehouse-transfers-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for name, ddl in TABLES.items():
        if name not in existing_tables:
            cur.execute(ddl)
            print(f'  + table {name} created')
        else:
            print(f'  = table {name} already present — skipped')

    existing_indexes = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    for name, ddl in INDEXES.items():
        if name not in existing_indexes:
            cur.execute(ddl)
            print(f'  + index {name} created')
        else:
            print(f'  = index {name} already present — skipped')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
