#!/usr/bin/env python
import sqlite3

db_path = 'instance/database.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('Checking table structures:\n')
for table in ['bom_items', 'manufacturing_orders', 'manufacturing_order_items']:
    cursor.execute(f"PRAGMA table_info('{table}');")
    columns = cursor.fetchall()
    col_names = [col[1] for col in columns]
    print(f'{table}:')
    print(f'  Columns: {col_names}')
    
    # Check for specific warehouse columns
    if table == 'bom_items':
        print(f'  Has warehouse_id: {"warehouse_id" in col_names}\n')
    elif table == 'manufacturing_orders':
        print(f'  Has finished_warehouse_id: {"finished_warehouse_id" in col_names}\n')
    elif table == 'manufacturing_order_items':
        print(f'  Has warehouse_id: {"warehouse_id" in col_names}\n')

conn.close()
