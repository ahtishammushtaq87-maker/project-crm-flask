"""
Migration: Create purchase_orders, purchase_order_items tables
         Add po_id column to purchase_bills
Run once: python add_purchase_orders.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import PurchaseOrder, PurchaseOrderItem, PurchaseBill
from sqlalchemy import inspect, text

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    existing = inspector.get_table_names()

    # Create all missing tables
    db.create_all()
    print("✅  db.create_all() completed.")

    # Verify new tables
    inspector2 = inspect(db.engine)
    tables_now = inspector2.get_table_names()
    for t in ('purchase_orders', 'purchase_order_items'):
        if t in tables_now:
            print(f"✅  Table '{t}' exists.")
        else:
            print(f"❌  Table '{t}' NOT found!")

    # Add po_id column to purchase_bills if missing
    pb_cols = [c['name'] for c in inspector2.get_columns('purchase_bills')]
    if 'po_id' not in pb_cols:
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE purchase_bills ADD COLUMN po_id INTEGER REFERENCES purchase_orders(id)"))
                conn.commit()
            print("✅  Added po_id column to purchase_bills.")
        except Exception as e:
            print(f"⚠️   po_id column issue (may already exist): {e}")
    else:
        print("✅  po_id column already present in purchase_bills.")

    print("\nMigration complete.")
