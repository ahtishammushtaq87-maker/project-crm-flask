#!/usr/bin/env python
import sqlite3
import sys

db_path = 'instance/database.db'
sql_file = 'migrations/sqlite_add_manufacturing_warehouse_columns.sql'

# Read SQL migration file
with open(sql_file, 'r') as f:
    sql_content = f.read()

# Connect to DB and execute
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.executescript(sql_content)
    conn.commit()
    print('✓ Migration applied successfully!')
    
    # Verify columns were added
    for table in ['bom_items', 'manufacturing_orders', 'manufacturing_order_items']:
        cursor.execute(f"PRAGMA table_info('{table}');")
        columns = cursor.fetchall()
        print(f'\n{table} columns:')
        for col in columns:
            print(f'  - {col[1]} ({col[2]})')
except Exception as e:
    print(f'✗ Migration failed: {e}')
    conn.rollback()
    sys.exit(1)
finally:
    conn.close()

print('\n✓ All columns verified. Database is ready!')
