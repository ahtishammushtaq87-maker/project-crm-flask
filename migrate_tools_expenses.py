import sqlite3
import os

def migrate():
    # Adjust this to your actual database path
    db_path = 'instance/database.db'
    if not os.path.exists(db_path):
        # Try finding it in the root if not in instance
        db_path = 'crm.db'
        if not os.path.exists(db_path):
            print("Database not found!")
            return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Adding columns to tool_delivering...")
        # Add shipping_charges and total_amount to tool_delivering
        try:
            cursor.execute("ALTER TABLE tool_delivering ADD COLUMN shipping_charges FLOAT DEFAULT 0.0")
        except sqlite3.OperationalError:
            print("Column shipping_charges already exists in tool_delivering")
            
        try:
            cursor.execute("ALTER TABLE tool_delivering ADD COLUMN total_amount FLOAT DEFAULT 0.0")
        except sqlite3.OperationalError:
            print("Column total_amount already exists in tool_delivering")

        print("Adding columns to tool_delivering_items...")
        # Add unit_price and total to tool_delivering_items
        try:
            cursor.execute("ALTER TABLE tool_delivering_items ADD COLUMN unit_price FLOAT DEFAULT 0.0")
        except sqlite3.OperationalError:
            print("Column unit_price already exists in tool_delivering_items")
            
        try:
            cursor.execute("ALTER TABLE tool_delivering_items ADD COLUMN total FLOAT DEFAULT 0.0")
        except sqlite3.OperationalError:
            print("Column total already exists in tool_delivering_items")

        conn.commit()
        print("Migration successful!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
