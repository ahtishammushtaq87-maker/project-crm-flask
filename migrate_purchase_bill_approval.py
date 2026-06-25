"""
Migration: Add approval columns to purchase_bills table
Run: python migrate_purchase_bill_approval.py
"""
import sqlite3
import os
import sys

# Detect DB path from common locations
db_paths = [
    os.path.join('instance', 'database.db'),
    os.path.join('instance', 'project_crm_flask.db'),
    os.path.join('instance', 'crm.db'),
    'project.db'
]

db_path = None
for p in db_paths:
    if os.path.exists(p):
        db_path = p
        break

if not db_path:
    print("❌  Could not find database file.")
    sys.exit(1)

print(f"📂 Using database: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if column already exists
cursor.execute("PRAGMA table_info(purchase_bills)")
columns = [col[1] for col in cursor.fetchall()]

new_columns = [
    ('is_approved', "INTEGER DEFAULT 1"), # BOOLEAN is INTEGER in SQLite
    ('is_rejected', "INTEGER DEFAULT 0"),
    ('rejection_reason', "TEXT"),
    ('approved_by', "INTEGER"),
    ('approved_at', "DATETIME")
]

added_any = False
for col_name, col_type in new_columns:
    if col_name in columns:
        print(f"✅  {col_name} column already exists in purchase_bills.")
    else:
        print(f"Adding {col_name}...")
        cursor.execute(f"ALTER TABLE purchase_bills ADD COLUMN {col_name} {col_type}")
        added_any = True

if added_any:
    conn.commit()
    print("✅  Added approval columns to purchase_bills.")
else:
    print("ℹ️ No new columns were added.")

conn.close()
print("🎉 Migration complete!")
