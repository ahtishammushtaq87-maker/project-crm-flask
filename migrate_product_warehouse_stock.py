"""
Migration: Add product_warehouse_stock table for per-warehouse quantity tracking.
Run this once before starting the app:
    python migrate_product_warehouse_stock.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from sqlalchemy import text

def run():
    app = create_app()
    with app.app_context():
        with db.engine.connect() as conn:
            # Create table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS product_warehouse_stock (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL REFERENCES products(id),
                    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                    quantity REAL DEFAULT 0,
                    UNIQUE (product_id, warehouse_id)
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pws_product ON product_warehouse_stock(product_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pws_warehouse ON product_warehouse_stock(warehouse_id)"))
            conn.commit()
        print("Migration complete: product_warehouse_stock table created.")

if __name__ == '__main__':
    run()
