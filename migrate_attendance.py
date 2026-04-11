#!/usr/bin/env python
"""
Migration script to create attendance table for time tracking
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from sqlalchemy import inspect, text

app = create_app()

def migrate():
    with app.app_context():
        # Check if table exists
        inspector = inspect(db.engine)
        tables = [t for t in inspector.get_table_names()]
        
        if 'attendance' in tables:
            print("✓ Table 'attendance' already exists")
            return
        
        # Create the table using SQLAlchemy
        try:
            from app.models import Attendance
            db.create_all()
            print("✓ Created 'attendance' table successfully")
            
            # Verify the table was created
            inspector = inspect(db.engine)
            if 'attendance' in inspector.get_table_names():
                columns = [c['name'] for c in inspector.get_columns('attendance')]
                print(f"✓ Table columns: {', '.join(columns)}")
            
        except Exception as e:
            print(f"✗ Error creating table: {e}")
            return
        
        print("\n✓ Migration completed successfully!")

if __name__ == '__main__':
    migrate()
