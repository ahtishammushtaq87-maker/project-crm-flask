"""
Migration: Add mo_id to expenses and actual_overhead_cost to manufacturing_orders
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    return column in cols

def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    changes = []

    # Add mo_id to expenses
    if not column_exists(cur, 'expenses', 'mo_id'):
        cur.execute("ALTER TABLE expenses ADD COLUMN mo_id INTEGER REFERENCES manufacturing_orders(id)")
        changes.append("Added mo_id to expenses")

    # Add actual_overhead_cost to manufacturing_orders
    if not column_exists(cur, 'manufacturing_orders', 'actual_overhead_cost'):
        cur.execute("ALTER TABLE manufacturing_orders ADD COLUMN actual_overhead_cost FLOAT DEFAULT 0")
        changes.append("Added actual_overhead_cost to manufacturing_orders")

    conn.commit()
    conn.close()

    if changes:
        for c in changes:
            print(f"[OK] {c}")
    else:
        print("[INFO] All columns already exist. No changes made.")

if __name__ == '__main__':
    run()
