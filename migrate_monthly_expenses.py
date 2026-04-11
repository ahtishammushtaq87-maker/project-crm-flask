#!/usr/bin/env python
"""
Migration script to add monthly division columns to expenses table
"""
import sys
sys.path.insert(0, '/d:/prefex_flask/project_crm_flask/project_crm_flask')

from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

def migrate():
    with app.app_context():
        # Check if columns already exist
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('expenses')]
        
        with db.engine.connect() as connection:
            # Add is_monthly_divided column if it doesn't exist
            if 'is_monthly_divided' not in columns:
                print("Adding is_monthly_divided column...")
                connection.execute(text("""
                    ALTER TABLE expenses ADD COLUMN is_monthly_divided BOOLEAN DEFAULT 0
                """))
                connection.commit()
                print("✓ Added is_monthly_divided column")
            else:
                print("✓ is_monthly_divided column already exists")
            
            # Add monthly_start_date column if it doesn't exist
            if 'monthly_start_date' not in columns:
                print("Adding monthly_start_date column...")
                connection.execute(text("""
                    ALTER TABLE expenses ADD COLUMN monthly_start_date DATE
                """))
                connection.commit()
                print("✓ Added monthly_start_date column")
            else:
                print("✓ monthly_start_date column already exists")
            
            # Add monthly_end_date column if it doesn't exist
            if 'monthly_end_date' not in columns:
                print("Adding monthly_end_date column...")
                connection.execute(text("""
                    ALTER TABLE expenses ADD COLUMN monthly_end_date DATE
                """))
                connection.commit()
                print("✓ Added monthly_end_date column")
            else:
                print("✓ monthly_end_date column already exists")
            
            # Add daily_amount column if it doesn't exist
            if 'daily_amount' not in columns:
                print("Adding daily_amount column...")
                connection.execute(text("""
                    ALTER TABLE expenses ADD COLUMN daily_amount FLOAT DEFAULT 0
                """))
                connection.commit()
                print("✓ Added daily_amount column")
            else:
                print("✓ daily_amount column already exists")
        
        print("\n✅ Migration completed successfully!")
        print("All monthly expense division columns have been added to the expenses table.")

if __name__ == '__main__':
    try:
        migrate()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
