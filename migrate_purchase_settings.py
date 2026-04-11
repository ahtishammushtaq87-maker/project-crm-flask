#!/usr/bin/env python
"""
Migration: Create purchase_settings table
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        sql = """
        CREATE TABLE IF NOT EXISTS purchase_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            default_notes TEXT,
            default_terms TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        db.session.execute(text(sql))
        db.session.commit()
        print("Created purchase_settings table")
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")

print("Migration complete!")
