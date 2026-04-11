#!/usr/bin/env python
"""
Migration: Add advance_applied to purchase_bills
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE purchase_bills ADD COLUMN advance_applied FLOAT DEFAULT 0'))
        db.session.commit()
        print("Added advance_applied column")
    except Exception as e:
        db.session.rollback()
        if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
            print("- advance_applied column already exists")
        else:
            print(f"Error: {e}")

print("Migration complete!")
