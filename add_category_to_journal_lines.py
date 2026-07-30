"""Migration script to add category_id column to journal_lines table."""
import sqlite3
import os

db_paths = [
    os.path.join(os.path.dirname(__file__), 'instance', 'crm.db'),
    os.path.join(os.path.dirname(__file__), 'crm.db')
]

for db_path in db_paths:
    if os.path.exists(db_path):
        print(f"Checking database at {db_path}...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(journal_lines);")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'category_id' not in columns:
            print("Adding category_id column to journal_lines table...")
            cursor.execute("ALTER TABLE journal_lines ADD COLUMN category_id INTEGER REFERENCES expense_categories(id);")
            conn.commit()
            print("category_id column added successfully.")
        else:
            print("category_id column already exists.")
            
        conn.close()
