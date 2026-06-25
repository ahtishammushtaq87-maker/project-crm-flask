import sqlite3
import os

db_path = os.path.join('instance', 'database.db')

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Adding 'stock_updated' column to 'sales' table...")
        cursor.execute("ALTER TABLE sales ADD COLUMN stock_updated BOOLEAN DEFAULT 0")
        conn.commit()
        print("Column added successfully.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Column 'stock_updated' already exists.")
        else:
            print(f"Error: {e}")
    
    conn.close()
