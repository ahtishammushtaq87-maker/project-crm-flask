import sqlite3
import os

# Database path
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'database.db')

def update_schema():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Checking for 'produced_qty' column in 'manufacturing_orders' table...")
    try:
        cursor.execute("SELECT produced_qty FROM manufacturing_orders LIMIT 1")
        print("'produced_qty' column already exists.")
    except sqlite3.OperationalError:
        print("Adding 'produced_qty' column to 'manufacturing_orders' table...")
        cursor.execute("ALTER TABLE manufacturing_orders ADD COLUMN produced_qty FLOAT DEFAULT 0")
        print("'produced_qty' column added.")

    print("Checking for 'manufacturing_order_history' table...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='manufacturing_order_history'")
    if not cursor.fetchone():
        print("Creating 'manufacturing_order_history' table...")
        cursor.execute('''
            CREATE TABLE manufacturing_order_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mo_id INTEGER NOT NULL,
                quantity_produced FLOAT NOT NULL,
                material_cost FLOAT DEFAULT 0,
                labor_cost FLOAT DEFAULT 0,
                overhead_cost FLOAT DEFAULT 0,
                total_cost FLOAT DEFAULT 0,
                completion_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                FOREIGN KEY (mo_id) REFERENCES manufacturing_orders (id),
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        ''')
        print("'manufacturing_order_history' table created.")
    else:
        print("'manufacturing_order_history' table already exists.")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    update_schema()
