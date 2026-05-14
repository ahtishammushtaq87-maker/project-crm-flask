#!/usr/bin/env python
"""
Migration script to add custom deduction columns to attendance table
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from sqlalchemy import inspect, text

app = create_app()

def migrate():
    with app.app_context():
        # Check columns for attendance table
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('attendance')]
        
        new_columns = [
            ('deduct_hours', 'FLOAT DEFAULT 0'),
            ('deduct_minutes', 'INTEGER DEFAULT 0'),
            ('deduct_reason', 'TEXT')
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in columns:
                print(f"Adding column '{col_name}' to 'attendance' table...")
                try:
                    db.session.execute(text(f"ALTER TABLE attendance ADD COLUMN {col_name} {col_type}"))
                    db.session.commit()
                    print(f"✓ Added '{col_name}' successfully")
                except Exception as e:
                    print(f"✗ Error adding column '{col_name}': {e}")
                    db.session.rollback()
            else:
                print(f"✓ Column '{col_name}' already exists")
        
        print("\n✓ Migration completed successfully!")

if __name__ == '__main__':
    migrate()
