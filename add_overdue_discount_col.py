
import sqlite3
import os

db_path = 'instance/database.db'

def add_column():
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(sales)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'ignore_overdue_discount' not in columns:
            print("Adding ignore_overdue_discount column to sales table...")
            cursor.execute("ALTER TABLE sales ADD COLUMN ignore_overdue_discount BOOLEAN DEFAULT 0")
            conn.commit()
            print("Column added successfully.")
        else:
            print("Column ignore_overdue_discount already exists.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    add_column()
