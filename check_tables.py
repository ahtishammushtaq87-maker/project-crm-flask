
import sqlite3
import os

paths = [
    os.path.join('instance', 'database.db'),
    os.path.join('instance', 'project.db'),
    'project.db'
]

for db_path in paths:
    if os.path.exists(db_path):
        print(f"Checking {db_path}...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables in {db_path}: {tables}")
        conn.close()
    else:
        print(f"{db_path} does not exist.")
