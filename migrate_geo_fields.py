import sqlite3
import os

db_path = os.path.join('instance', 'database.db')

def migrate():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Columns to add
    columns = [
        ('vendors', 'state', 'TEXT'),
        ('vendors', 'country', 'TEXT'),
        ('customers', 'state', 'TEXT'),
        ('customers', 'country', 'TEXT')
    ]

    for table, col_name, col_type in columns:
        try:
            # Check if column exists
            cursor.execute(f"PRAGMA table_info({table})")
            existing_cols = [c[1] for c in cursor.fetchall()]
            
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                print(f"Added column {col_name} to {table}")
            else:
                print(f"Column {col_name} already exists in {table}")
        except Exception as e:
            print(f"Error adding {col_name} to {table}: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
