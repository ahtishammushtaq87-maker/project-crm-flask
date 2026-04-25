import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, 'instance', 'database.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE vendors ADD COLUMN payment_method VARCHAR(50)')
    print('✅ added payment_method to vendors')
except Exception as e:
    print('❌ ALTER vendors failed (might already exist):', e)

try:
    cursor.execute('ALTER TABLE customers ADD COLUMN payment_method VARCHAR(50)')
    print('✅ added payment_method to customers')
except Exception as e:
    print('❌ ALTER customers failed (might already exist):', e)

conn.commit()
conn.close()
