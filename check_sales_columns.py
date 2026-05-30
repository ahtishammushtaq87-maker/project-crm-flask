import sqlite3
import os

db_path = 'project.db' # Based on list_dir, project.db is in root. Wait, let me check instance/ too.
if not os.path.exists(db_path):
    db_path = 'instance/project.db'
if not os.path.exists(db_path):
    db_path = 'instance/database.db'

print(f"Checking database: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(sales)")
columns = cursor.fetchall()
for col in columns:
    print(col)

conn.close()
