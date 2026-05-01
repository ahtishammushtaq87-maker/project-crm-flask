import sqlite3
import os

databases = ['instance/crm.db', 'instance/database.db', 'instance/project_crm.db']

for db_path in databases:
    if os.path.exists(db_path):
        print(f"\nTables in {db_path}:")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        conn.close()
    else:
        print(f"\n{db_path} does not exist.")
