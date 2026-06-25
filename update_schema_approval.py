import sqlite3
import os

db_path = 'instance/database.db'

def update_schema():
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables_to_update = {
        'expenses': [
            ('is_approved', 'BOOLEAN DEFAULT 0'),
            ('is_rejected', 'BOOLEAN DEFAULT 0'),
            ('rejection_reason', 'TEXT'),
            ('approved_by', 'INTEGER REFERENCES users(id)'),
            ('approved_at', 'DATETIME')
        ],
        'sale_returns': [
            ('is_approved', 'BOOLEAN DEFAULT 0'),
            ('is_rejected', 'BOOLEAN DEFAULT 0'),
            ('rejection_reason', 'TEXT'),
            ('approved_by', 'INTEGER REFERENCES users(id)'),
            ('approved_at', 'DATETIME')
        ],
        'purchase_returns': [
            ('is_approved', 'BOOLEAN DEFAULT 0'),
            ('is_rejected', 'BOOLEAN DEFAULT 0'),
            ('rejection_reason', 'TEXT'),
            ('approved_by', 'INTEGER REFERENCES users(id)'),
            ('approved_at', 'DATETIME')
        ],
        'vendor_advances': [
            ('is_approved', 'BOOLEAN DEFAULT 0'),
            ('is_rejected', 'BOOLEAN DEFAULT 0'),
            ('rejection_reason', 'TEXT'),
            ('approved_by', 'INTEGER REFERENCES users(id)'),
            ('approved_at', 'DATETIME')
        ]
    }

    for table, columns in tables_to_update.items():
        # Check existing columns
        cursor.execute(f"PRAGMA table_info({table})")
        existing_cols = [row[1] for row in cursor.fetchall()]
        
        for col_name, col_type in columns:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                    print(f"Added column {col_name} to {table}")
                except Exception as e:
                    print(f"Error adding {col_name} to {table}: {e}")
            else:
                print(f"Column {col_name} already exists in {table}")
        
        # Initialize existing records as approved if status is 'confirmed' (for expenses) or 'approved' (returns)
        if table == 'expenses':
            cursor.execute("UPDATE expenses SET is_approved = 1 WHERE status = 'confirmed'")
        elif table == 'sale_returns':
            cursor.execute("UPDATE sale_returns SET is_approved = 1 WHERE status = 'approved'")
        elif table == 'purchase_returns':
            cursor.execute("UPDATE purchase_returns SET is_approved = 1 WHERE status = 'approved'")
        # Default others to approved if created_at exists? 
        # For simplicity, let's assume old vendor_advances were approved since they didn't have approval workflow
        elif table == 'vendor_advances':
             cursor.execute("UPDATE vendor_advances SET is_approved = 1")

    conn.commit()
    conn.close()
    print("Schema update completed successfully.")

if __name__ == '__main__':
    update_schema()
