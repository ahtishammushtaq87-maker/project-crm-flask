#!/usr/bin/env python
"""
Migration: Add task settings table and email_sent field to tasks
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # 1. Add is_email_sent to tasks table
    try:
        db.session.execute(text('ALTER TABLE tasks ADD COLUMN is_email_sent BOOLEAN DEFAULT 0'))
        db.session.commit()
        print("Added is_email_sent column to tasks")
    except Exception as e:
        db.session.rollback()
        if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
            print("- is_email_sent column already exists")
        else:
            print(f"Error is_email_sent: {e}")

    # 2. Create task_settings table
    try:
        db.session.execute(text('''
            CREATE TABLE IF NOT EXISTS task_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                smtp_server VARCHAR(120),
                smtp_port INTEGER,
                smtp_user VARCHAR(120),
                smtp_password VARCHAR(120),
                sender_email VARCHAR(120),
                notification_email VARCHAR(120),
                is_enabled BOOLEAN DEFAULT 0,
                updated_at DATETIME
            )
        '''))
        db.session.commit()
        print("Created task_settings table")
        
        # Initialize with a default row if empty
        result = db.session.execute(text('SELECT COUNT(*) FROM task_settings')).fetchone()
        if result[0] == 0:
            db.session.execute(text('''
                INSERT INTO task_settings (smtp_server, smtp_port, is_enabled, updated_at)
                VALUES ('smtp.gmail.com', 587, 0, CURRENT_TIMESTAMP)
            '''))
            db.session.commit()
            print("Initialized default task settings")
            
    except Exception as e:
        db.session.rollback()
        print(f"Error task_settings table: {e}")

print("Migration complete!")
