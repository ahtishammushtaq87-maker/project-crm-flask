import sqlite3
import os

db_path = os.path.join('instance', 'database.db')

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(customers)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'sub_customers' not in columns:
            print("Adding 'sub_customers' column to 'customers' table...")
            cursor.execute("ALTER TABLE customers ADD COLUMN sub_customers TEXT")
            conn.commit()
            print("Column added successfully.")
        else:
            print("'sub_customers' column already exists.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
else:
    print(f"Database file {db_path} not found.")
