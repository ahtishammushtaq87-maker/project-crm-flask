import sqlite3
import os

def migrate():
    db_path = os.path.join('instance', 'database.db')
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    columns_to_add = [
        ('city', 'VARCHAR(100)'),
        ('postal_code', 'VARCHAR(20)'),
        ('sub_vendors', 'TEXT')
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE vendors ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to vendors table.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column {col_name} already exists in vendors table.")
            else:
                print(f"Error adding column {col_name}: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
