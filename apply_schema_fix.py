import sqlite3
from sqlalchemy import create_engine, text
print('--- DIRECT SQLITE CHECK ---')
conn_sqlite = sqlite3.connect('database.db')
cursor = conn_sqlite.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('tables:', [r[0] for r in cursor.fetchall()])
conn_sqlite.close()

engine = create_engine('sqlite:///database.db')
conn = engine.connect()
cols = [c[1] for c in conn.execute(text('PRAGMA table_info(sales)'))]
print('before', cols)
try:
    conn.execute(text('ALTER TABLE sales ADD COLUMN vendor_id INTEGER'))
    print('added vendor_id')
except Exception as e:
    print('ALTER failed:', e)
cols = [c[1] for c in conn.execute(text('PRAGMA table_info(sales)'))]
print('after', cols)
conn.close()
