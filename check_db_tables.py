import sqlite3
for db in ['project.db', 'instance/project.db', 'instance/database.db']:
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables in {db}: {tables}")
        if any('sales' in t[0] for t in tables):
            cursor.execute("PRAGMA table_info(sales)")
            print(f"Columns in sales table in {db}: {[c[1] for c in cursor.fetchall()]}")
        conn.close()
    except Exception as e:
        print(f"Error checking {db}: {e}")
