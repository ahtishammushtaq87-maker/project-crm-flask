"""
Migration: Add task_group_name and linked_invoice_id columns to tasks table.
Uses Flask app context so the DB path is resolved correctly.
Safe to run multiple times.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
import sqlite3

app = create_app()

with app.app_context():
    # Get the actual DB path from SQLAlchemy
    db_uri = db.engine.url
    db_path = str(db_uri).replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), db_path)

    print(f"DB path: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(tasks)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Existing columns in 'tasks': {columns}")

    added = []

    if 'task_group_name' not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN task_group_name VARCHAR(100)")
        added.append('task_group_name')
        print("  + Added column: task_group_name")
    else:
        print("  - Column already exists: task_group_name")

    if 'linked_invoice_id' not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN linked_invoice_id INTEGER REFERENCES sales(id)")
        added.append('linked_invoice_id')
        print("  + Added column: linked_invoice_id")
    else:
        print("  - Column already exists: linked_invoice_id")

    conn.commit()
    conn.close()

    if added:
        print(f"\nMigration complete. Added: {', '.join(added)}")
    else:
        print("\nMigration complete. No changes needed.")
