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
        cursor.execute("PRAGMA table_info(sales)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'installment_schedule' not in columns:
            print("Adding installment_schedule column to sales table...")
            cursor.execute("ALTER TABLE sales ADD COLUMN installment_schedule TEXT")
            conn.commit()
            print("Migration completed successfully.")
        else:
            print("Column installment_schedule already exists.")

    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
