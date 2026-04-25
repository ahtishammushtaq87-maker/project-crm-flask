"""
Migration: Add bill_image_path column to purchase_bills table
Run: python migrate_purchase_bill_image.py
"""
import sqlite3
import os
import sys

# Detect DB path from common locations
# database.db is the primary DB per config.py
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
cursor.execute("PRAGMA table_info(purchase_bills)")
columns = [col[1] for col in cursor.fetchall()]

if 'bill_image_path' in columns:
    print("✅  bill_image_path column already exists in purchase_bills.")
else:
    cursor.execute("ALTER TABLE purchase_bills ADD COLUMN bill_image_path VARCHAR(255)")
    conn.commit()
    print("✅  Added bill_image_path column to purchase_bills.")

conn.close()
print("🎉 Migration complete!")

