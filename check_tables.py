#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('instance/crm.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print('Tables in database:')
for table in tables:
    print(f'  - {table[0]}')
conn.close()
