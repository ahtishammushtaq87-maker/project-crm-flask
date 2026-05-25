"""
Migration: Add image_path, city, postal_code columns to customers table.
Safe to run multiple times (checks if columns already exist before adding).
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')
# Fallback paths
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'project.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), 'project.db')

print(f"Using database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Inspect existing columns
cur.execute("PRAGMA table_info(customers)")
existing_cols = {row[1] for row in cur.fetchall()}
print(f"Existing columns: {existing_cols}")

changes = 0

if 'image_path' not in existing_cols:
    cur.execute("ALTER TABLE customers ADD COLUMN image_path VARCHAR(255)")
    print("  + Added column: image_path")
    changes += 1
else:
    print("  - Skipped (already exists): image_path")

if 'city' not in existing_cols:
    cur.execute("ALTER TABLE customers ADD COLUMN city VARCHAR(100)")
    print("  + Added column: city")
    changes += 1
else:
    print("  - Skipped (already exists): city")

if 'postal_code' not in existing_cols:
    cur.execute("ALTER TABLE customers ADD COLUMN postal_code VARCHAR(20)")
    print("  + Added column: postal_code")
    changes += 1
else:
    print("  - Skipped (already exists): postal_code")

conn.commit()
conn.close()

if changes:
    print(f"\nMigration complete. {changes} column(s) added.")
else:
    print("\nNothing to do — all columns already present.")
