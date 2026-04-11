#!/usr/bin/env python
"""
Migration: Add BOM versioning system and shipping tracking
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # 1. Add shipping_charge to purchase_items
        print("Adding shipping_charge to purchase_items...")
        try:
            db.session.execute(text("ALTER TABLE purchase_items ADD COLUMN shipping_charge FLOAT DEFAULT 0"))
            db.session.commit()
            print("✓ Added shipping_charge to purchase_items")
        except Exception as e:
            if 'duplicate column' in str(e).lower():
                print("✓ shipping_charge already exists")
            else:
                raise
        
        # 2. Create bom_versions table
        print("\nCreating bom_versions table...")
        sql_versions = """
        CREATE TABLE IF NOT EXISTS bom_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bom_id INTEGER NOT NULL,
            version_number VARCHAR(10) NOT NULL,
            labor_cost FLOAT DEFAULT 0,
            overhead_cost FLOAT DEFAULT 0,
            total_cost FLOAT DEFAULT 0,
            change_reason VARCHAR(200),
            change_type VARCHAR(50),
            previous_version VARCHAR(10),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (bom_id) REFERENCES boms(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        """
        db.session.execute(text(sql_versions))
        db.session.commit()
        print("✓ Created bom_versions table")
        
        # 3. Create bom_version_items table
        print("Creating bom_version_items table...")
        sql_version_items = """
        CREATE TABLE IF NOT EXISTS bom_version_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            component_id INTEGER NOT NULL,
            quantity FLOAT NOT NULL,
            unit_cost FLOAT DEFAULT 0,
            shipping_per_unit FLOAT DEFAULT 0,
            total_cost FLOAT DEFAULT 0,
            FOREIGN KEY (version_id) REFERENCES bom_versions(id),
            FOREIGN KEY (component_id) REFERENCES products(id)
        )
        """
        db.session.execute(text(sql_version_items))
        db.session.commit()
        print("✓ Created bom_version_items table")
        
        # 4. Modify bom_items table to add new columns
        print("\nUpdating bom_items table...")
        try:
            db.session.execute(text("ALTER TABLE bom_items RENAME COLUMN cost TO unit_cost"))
            print("✓ Renamed cost to unit_cost")
        except Exception as e:
            if 'no such column' in str(e).lower() or 'duplicate column' in str(e).lower():
                print("✓ Column already updated")
            else:
                print(f"⚠ Could not rename: {e}")
        
        try:
            db.session.execute(text("ALTER TABLE bom_items ADD COLUMN shipping_per_unit FLOAT DEFAULT 0"))
            db.session.commit()
            print("✓ Added shipping_per_unit to bom_items")
        except Exception as e:
            if 'duplicate column' in str(e).lower():
                print("✓ shipping_per_unit already exists")
            else:
                raise
        
        try:
            db.session.execute(text("ALTER TABLE bom_items ADD COLUMN total_cost FLOAT DEFAULT 0"))
            db.session.commit()
            print("✓ Added total_cost to bom_items")
        except Exception as e:
            if 'duplicate column' in str(e).lower():
                print("✓ total_cost already exists")
            else:
                raise
        
        try:
            db.session.execute(text("ALTER TABLE bom_items ADD COLUMN cost_price_history_id INTEGER"))
            db.session.commit()
            print("✓ Added cost_price_history_id to bom_items")
        except Exception as e:
            if 'duplicate column' in str(e).lower():
                print("✓ cost_price_history_id already exists")
            else:
                raise
        
        # 5. Modify boms table to add version tracking
        print("\nUpdating boms table...")
        try:
            db.session.execute(text("ALTER TABLE boms ADD COLUMN version VARCHAR(10) DEFAULT 'v1'"))
            db.session.commit()
            print("✓ Added version to boms")
        except Exception as e:
            if 'duplicate column' in str(e).lower():
                print("✓ version already exists")
            else:
                raise
        
        try:
            db.session.execute(text("ALTER TABLE boms ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            db.session.commit()
            print("✓ Added is_active to boms")
        except Exception as e:
            if 'duplicate column' in str(e).lower():
                print("✓ is_active already exists")
            else:
                raise
        
        # 6. Create indices for performance
        print("\nCreating indices...")
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_bom_versions_bom ON bom_versions(bom_id)",
            "CREATE INDEX IF NOT EXISTS idx_bom_version_items_version ON bom_version_items(version_id)",
            "CREATE INDEX IF NOT EXISTS idx_bom_items_unit_cost ON bom_items(unit_cost)",
            "CREATE INDEX IF NOT EXISTS idx_bom_version_column ON boms(version)",
        ]
        
        for idx_sql in indices:
            db.session.execute(text(idx_sql))
        db.session.commit()
        print("✓ Created indices")
        
        print("\n" + "="*60)
        print("✓ Migration complete!")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ Error during migration: {e}")
        db.session.rollback()
        raise
