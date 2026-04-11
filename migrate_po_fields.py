#!/usr/bin/env python
"""
Migration: Add delivery time window and advance amount to purchase_orders
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Add delivery_start column
    try:
        db.session.execute(text('ALTER TABLE purchase_orders ADD COLUMN delivery_start DATETIME'))
        db.session.commit()
        print("Added delivery_start column")
    except Exception as e:
        db.session.rollback()
        if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
            print("- delivery_start column already exists")
        else:
            print(f"Error delivery_start: {e}")

    # Add delivery_end column
    try:
        db.session.execute(text('ALTER TABLE purchase_orders ADD COLUMN delivery_end DATETIME'))
        db.session.commit()
        print("Added delivery_end column")
    except Exception as e:
        db.session.rollback()
        if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
            print("- delivery_end column already exists")
        else:
            print(f"Error delivery_end: {e}")

    # Add advance_amount column
    try:
        db.session.execute(text('ALTER TABLE purchase_orders ADD COLUMN advance_amount FLOAT DEFAULT 0'))
        db.session.commit()
        print("Added advance_amount column")
    except Exception as e:
        db.session.rollback()
        if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
            print("- advance_amount column already exists")
        else:
            print(f"Error advance_amount: {e}")

print("Migration complete!")
