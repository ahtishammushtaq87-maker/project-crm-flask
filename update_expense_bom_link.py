import sqlite3
import os

def update_db():
    db_path = 'instance/database.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add bom_id column to expenses table (linked to BOMs)
        cursor.execute("ALTER TABLE expenses ADD COLUMN bom_id INTEGER REFERENCES boms(id)")
        conn.commit()
        print("Column 'bom_id' added to 'expenses' table successfully.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Column 'bom_id' already exists.")
        else:
            print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_db()
