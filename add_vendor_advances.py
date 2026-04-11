"""
Migration script: Create vendor_advances table
Run once: python add_vendor_advances.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import VendorAdvance

app = create_app()

with app.app_context():
    try:
        db.create_all()
        print("✅  vendor_advances table created (or already exists).")

        # Verify the table exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if 'vendor_advances' in tables:
            print("✅  Verified: vendor_advances table is present in the database.")
        else:
            print("❌  Table vendor_advances was NOT found — check for errors above.")
    except Exception as e:
        print(f"❌  Error: {e}")
        import traceback
        traceback.print_exc()
