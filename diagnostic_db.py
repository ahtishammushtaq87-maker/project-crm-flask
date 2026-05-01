import sqlite3
import os

with open('db_diagnostic.txt', 'w') as f:
    for db in ['instance/database.db', 'instance/project_crm.db', 'instance/crm.db']:
        if os.path.exists(db):
            f.write(f"\nDB: {db}\n")
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cur.fetchall()]
            f.write(f"Tables: {', '.join(tables)}\n")
            
            if 'salesmen' in tables:
                cur.execute("PRAGMA table_info(salesmen)")
                cols = [c[1] for c in cur.fetchall()]
                f.write(f"Salesmen columns: {', '.join(cols)}\n")
            conn.close()
        else:
            f.write(f"\nDB: {db} does not exist\n")
