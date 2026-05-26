import sqlite3
import os

def migrate():
    db_path = os.path.join('instance', 'database.db')
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables_to_check = {
        'bill_receive_items': 'warehouse_id',
        'purchase_items': 'warehouse_id',
        'purchase_order_items': 'warehouse_id'
    }

    for table, column in tables_to_check.items():
        try:
            # Check if column exists
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [info[1] for info in cursor.fetchall()]
            
            if column not in columns:
                print(f"Adding {column} to {table}...")
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER REFERENCES warehouses(id)")
                conn.commit()
                print(f"Successfully added {column} to {table}.")
            else:
                print(f"Column {column} already exists in {table}.")
        except Exception as e:
            print(f"Error updating {table}: {e}")

    conn.close()

if __name__ == '__main__':
    migrate()
