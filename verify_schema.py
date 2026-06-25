import sqlite3

db_path = 'instance/database.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables = ['expenses', 'sale_returns', 'purchase_returns', 'vendor_advances']

for table in tables:
    print(f"\nTable: {table}")
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    new_cols = ['is_approved', 'is_rejected', 'rejection_reason', 'approved_by', 'approved_at']
    for col in new_cols:
        if col in cols:
            print(f"  [OK] {col}")
        else:
            print(f"  [MISSING] {col}")

conn.close()
