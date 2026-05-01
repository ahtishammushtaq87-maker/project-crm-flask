import sqlite3
def check(path):
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cur.fetchall()]
        print(f"{path}: {tables}")
        conn.close()
    except Exception as e:
        print(f"Error {path}: {e}")

check('instance/database.db')
check('instance/project_crm.db')
check('instance/crm.db')
