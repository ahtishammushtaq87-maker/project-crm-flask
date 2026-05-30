import sqlite3
import os

db_path = 'instance/database.db'

def migrate():
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(sales)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'overdue_date' not in columns:
            print("Adding overdue_date column to sales table...")
            cursor.execute("ALTER TABLE sales ADD COLUMN overdue_date DATETIME")
            
            # Populate overdue_date with due_date for existing records
            print("Populating overdue_date with due_date for existing records...")
            cursor.execute("UPDATE sales SET overdue_date = due_date WHERE due_date IS NOT NULL")
            
            conn.commit()
            print("Migration completed successfully.")
        else:
            print("Column overdue_date already exists.")
            
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
