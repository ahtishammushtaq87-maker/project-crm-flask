#!/usr/bin/env python
"""
Migration: Add cost_price_history table to track cost price changes
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Create the cost_price_history table
        sql = """
        CREATE TABLE IF NOT EXISTS cost_price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            purchase_bill_id INTEGER,
            old_price FLOAT,
            new_price FLOAT NOT NULL,
            quantity_at_old_price FLOAT DEFAULT 0,
            used_quantity FLOAT DEFAULT 0,
            change_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            reason VARCHAR(200),
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (purchase_bill_id) REFERENCES purchase_bills(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        """
        
        db.session.execute(text(sql))
        db.session.commit()
        print("✓ Created cost_price_history table successfully")
        
        # Create indices
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_cph_product ON cost_price_history(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_cph_bill ON cost_price_history(purchase_bill_id)",
            "CREATE INDEX IF NOT EXISTS idx_cph_date ON cost_price_history(change_date)",
        ]
        
        for idx_sql in indices:
            db.session.execute(text(idx_sql))
        db.session.commit()
        print("✓ Created indices successfully")
        
    except Exception as e:
        print(f"✗ Error during migration: {e}")
        db.session.rollback()
        raise

print("✓ Migration complete!")
