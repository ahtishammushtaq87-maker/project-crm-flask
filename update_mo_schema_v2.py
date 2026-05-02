import sqlite3
import os

db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'database.db')

def update_schema():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Checking for 'is_manual_overhead' column in 'manufacturing_order_history' table...")
    try:
        cursor.execute("SELECT is_manual_overhead FROM manufacturing_order_history LIMIT 1")
        print("'is_manual_overhead' column already exists.")
    except sqlite3.OperationalError:
        print("Adding 'is_manual_overhead' column to 'manufacturing_order_history' table...")
        cursor.execute("ALTER TABLE manufacturing_order_history ADD COLUMN is_manual_overhead BOOLEAN DEFAULT 0")
        print("'is_manual_overhead' column added.")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    update_schema()
