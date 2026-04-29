"""
Migration: Add bill_payments, bill_receives, bill_receive_items tables
         + inventory_received column to purchase_bills

Safe to run multiple times (checks for column/table existence before adding).
"""

import sqlite3
import os

# Find the database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'crm.db')

if not os.path.exists(DB_PATH):
    # Try alternate db name
    for fname in os.listdir(os.path.join(BASE_DIR, 'instance')):
        if fname.endswith('.db'):
            DB_PATH = os.path.join(BASE_DIR, 'instance', fname)
            break

print(f"Using database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ── 1. Add inventory_received to purchase_bills ─────────────────────────────
cursor.execute("PRAGMA table_info(purchase_bills)")
bill_cols = [row[1] for row in cursor.fetchall()]

if 'inventory_received' not in bill_cols:
    cursor.execute("ALTER TABLE purchase_bills ADD COLUMN inventory_received BOOLEAN DEFAULT 0")
    print("✅ Added 'inventory_received' column to purchase_bills")
    # Mark ALL existing bills as already received (they already have inventory added)
    cursor.execute("UPDATE purchase_bills SET inventory_received = 1")
    print(f"✅ Marked all existing bills as inventory_received=True")
else:
    print("ⓘ  'inventory_received' column already exists in purchase_bills")

# ── 2. Create bill_payments table ──────────────────────────────────────────
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bill_payments'")
if not cursor.fetchone():
    cursor.execute("""
        CREATE TABLE bill_payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id      INTEGER NOT NULL REFERENCES purchase_bills(id),
            date         DATETIME DEFAULT CURRENT_TIMESTAMP,
            amount       REAL NOT NULL,
            payment_method VARCHAR(50) DEFAULT 'Cash',
            reference_number VARCHAR(100),
            notes        TEXT,
            image_path   VARCHAR(255),
            created_by   INTEGER REFERENCES users(id),
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_bill_payments_bill_id ON bill_payments(bill_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_bill_payments_date ON bill_payments(date)")
    print("✅ Created 'bill_payments' table")
else:
    print("ⓘ  'bill_payments' table already exists")

# ── 3. Create bill_receives table ──────────────────────────────────────────
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bill_receives'")
if not cursor.fetchone():
    cursor.execute("""
        CREATE TABLE bill_receives (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id    INTEGER NOT NULL REFERENCES purchase_bills(id),
            date       DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes      TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_bill_receives_bill_id ON bill_receives(bill_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_bill_receives_date ON bill_receives(date)")
    print("✅ Created 'bill_receives' table")
else:
    print("ⓘ  'bill_receives' table already exists")

# ── 4. Create bill_receive_items table ─────────────────────────────────────
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bill_receive_items'")
if not cursor.fetchone():
    cursor.execute("""
        CREATE TABLE bill_receive_items (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            receive_id         INTEGER NOT NULL REFERENCES bill_receives(id),
            purchase_item_id   INTEGER NOT NULL REFERENCES purchase_items(id),
            product_id         INTEGER NOT NULL REFERENCES products(id),
            quantity_received  REAL NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_bill_receive_items_receive_id ON bill_receive_items(receive_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_bill_receive_items_product_id ON bill_receive_items(product_id)")
    print("✅ Created 'bill_receive_items' table")
else:
    print("ⓘ  'bill_receive_items' table already exists")

conn.commit()
conn.close()
print("\n✅ Migration complete!")
print("   - All existing bills marked as inventory_received=True (no inventory data lost)")
print("   - New bills created from now on will NOT auto-update inventory on create")
print("   - Use 'Receive Quantity' on bill detail page to update inventory")
