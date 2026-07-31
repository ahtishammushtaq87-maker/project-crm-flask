"""Migration script to add bill_image_path column to journal_lines table."""
import sqlite3
import os

db_paths = [
    os.path.join(os.path.dirname(__file__), 'instance', 'database.db'),
    os.path.join(os.path.dirname(__file__), 'instance', 'crm.db'),
    os.path.join(os.path.dirname(__file__), 'instance', 'project.db'),
    os.path.join(os.path.dirname(__file__), 'instance', 'project_crm.db'),
    os.path.join(os.path.dirname(__file__), 'crm.db'),
    os.path.join(os.path.dirname(__file__), 'project.db'),
]

for db_path in db_paths:
    if os.path.exists(db_path):
        print(f"Checking database at {db_path}...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='journal_lines';")
        if not cursor.fetchone():
            print("No journal_lines table here, skipping.")
            conn.close()
            continue

        cursor.execute("PRAGMA table_info(journal_lines);")
        columns = [column[1] for column in cursor.fetchall()]

        if 'bill_image_path' not in columns:
            print("Adding bill_image_path column to journal_lines table...")
            cursor.execute("ALTER TABLE journal_lines ADD COLUMN bill_image_path VARCHAR(255);")
            conn.commit()
            print("bill_image_path column added successfully.")
        else:
            print("bill_image_path column already exists.")

        conn.close()
