import sqlite3
import os

def update_db():
    db_path = 'database.db'
    if not os.path.exists(db_path):
        db_path = os.path.join('instance', 'database.db')
        if not os.path.exists(db_path):
            print(f"Error: Could not find database file at database.db or {db_path}")
            return False

    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add is_manufactured column to products if it doesn't exist
        cursor.execute("PRAGMA table_info(products)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_manufactured' not in columns:
            print("Adding 'is_manufactured' column to products table...")
            cursor.execute("ALTER TABLE products ADD COLUMN is_manufactured BOOLEAN DEFAULT 0")
        else:
            print("'is_manufactured' column already exists in products table.")

        # Create manufacturing tables
        print("Creating boms table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS boms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                product_id INTEGER NOT NULL,
                labor_cost FLOAT DEFAULT 0,
                overhead_cost FLOAT DEFAULT 0,
                total_cost FLOAT DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        """)

        print("Creating bom_items table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bom_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bom_id INTEGER NOT NULL,
                component_id INTEGER NOT NULL,
                quantity FLOAT NOT NULL,
                cost FLOAT DEFAULT 0,
                FOREIGN KEY(bom_id) REFERENCES boms(id),
                FOREIGN KEY(component_id) REFERENCES products(id)
            )
        """)

        print("Creating manufacturing_orders table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manufacturing_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number VARCHAR(50) NOT NULL UNIQUE,
                bom_id INTEGER NOT NULL,
                status VARCHAR(20) DEFAULT 'Draft',
                quantity_to_produce FLOAT NOT NULL,
                start_date DATE,
                end_date DATE,
                actual_labor_cost FLOAT DEFAULT 0,
                actual_material_cost FLOAT DEFAULT 0,
                total_cost FLOAT DEFAULT 0,
                created_by INTEGER,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(bom_id) REFERENCES boms(id),
                FOREIGN KEY(created_by) REFERENCES users(id)
            )
        """)

        print("Creating manufacturing_order_items table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manufacturing_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mo_id INTEGER NOT NULL,
                component_id INTEGER NOT NULL,
                quantity_required FLOAT NOT NULL,
                quantity_consumed FLOAT DEFAULT 0,
                cost FLOAT DEFAULT 0,
                FOREIGN KEY(mo_id) REFERENCES manufacturing_orders(id),
                FOREIGN KEY(component_id) REFERENCES products(id)
            )
        """)

        # Add indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_boms_product_id ON boms(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_bom_items_bom_id ON bom_items(bom_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_bom_items_component_id ON bom_items(component_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_manufacturing_orders_order_number ON manufacturing_orders(order_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_manufacturing_orders_bom_id ON manufacturing_orders(bom_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_manufacturing_order_items_mo_id ON manufacturing_order_items(mo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_manufacturing_order_items_component_id ON manufacturing_order_items(component_id)")

        conn.commit()
        print("Database update successful!")
        return True
    
    except Exception as e:
        conn.rollback()
        print(f"Error updating database: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    update_db()
