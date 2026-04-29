"""
Migration: Add image_path column to payments table
Run: python migrate_payment_image.py
"""
import sqlite3
import os
import sys

# Detect DB path from common locations
db_paths = [
    os.path.join('instance', 'database.db'),
    os.path.join('instance', 'crm.db'),
    os.path.join('instance', 'project_crm_flask.db'),
]

db_path = None
for p in db_paths:
    if os.path.exists(p):
        db_path = p
        break

if not db_path:
    print("❌  Could not find database file in instance/ folder.")
    sys.exit(1)

print(f"📂 Using database: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if column already exists
cursor.execute("PRAGMA table_info(payments)")
columns = [col[1] for col in cursor.fetchall()]

if 'image_path' in columns:
    print("✅  image_path column already exists in payments.")
else:
    cursor.execute("ALTER TABLE payments ADD COLUMN image_path VARCHAR(255)")
    conn.commit()
    print("✅  Added image_path column to payments.")

conn.close()
print("🎉 Migration complete!")

