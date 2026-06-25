import sqlite3, os

dbs = [
    'instance/project_crm.db',
    'instance/crm.db',
    'instance/project.db',
    'project.db',
]
for db in dbs:
    try:
        conn = sqlite3.connect(db)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in c.fetchall()]
        print(f"{db}: {len(tables)} tables")
        if tables:
            print(f"  First 10: {tables[:10]}")
        conn.close()
    except Exception as e:
        print(f"{db}: ERROR - {e}")
