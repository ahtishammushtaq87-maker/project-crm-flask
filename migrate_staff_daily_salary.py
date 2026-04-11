#!/usr/bin/env python
"""
Migration script to add daily_salary column to staff table
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from sqlalchemy import inspect, text

app = create_app()

def migrate():
    with app.app_context():
        # Check if column exists
        inspector = inspect(db.engine)
        staff_columns = [c['name'] for c in inspector.get_columns('staff')]
        
        if 'daily_salary' in staff_columns:
            print("✓ Column 'daily_salary' already exists in staff table")
            return
        
        # Add the column
        try:
            with db.engine.connect() as connection:
                connection.execute(text('ALTER TABLE staff ADD COLUMN daily_salary FLOAT DEFAULT 0'))
                connection.commit()
            print("✓ Added 'daily_salary' column to staff table")
        except Exception as e:
            print(f"✗ Error adding column: {e}")
            return
        
        # Update existing staff - calculate daily salary
        from app.models import Staff
        try:
            all_staff = Staff.query.all()
            for staff in all_staff:
                staff.calculate_daily_salary()
            db.session.commit()
            print(f"✓ Calculated daily salary for {len(all_staff)} staff members")
        except Exception as e:
            print(f"✗ Error updating staff: {e}")
            db.session.rollback()
            return
        
        print("\n✓ Migration completed successfully!")

if __name__ == '__main__':
    migrate()
