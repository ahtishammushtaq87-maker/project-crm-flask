import sqlite3
import os

# Get the database path
db_path = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def column_exists(table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

try:
    # Check and add currency_id and exchange_rate to sales table
    if not column_exists('sales', 'currency_id'):
        cursor.execute("ALTER TABLE sales ADD COLUMN currency_id INTEGER REFERENCES currencies(id)")
        print("Added currency_id to sales")
    else:
        print("currency_id already exists in sales")

    if not column_exists('sales', 'exchange_rate'):
        cursor.execute("ALTER TABLE sales ADD COLUMN exchange_rate REAL DEFAULT 1.0")
        print("Added exchange_rate to sales")
    else:
        print("exchange_rate already exists in sales")

    # Check and add currency_id and exchange_rate to purchase_bills table
    if not column_exists('purchase_bills', 'currency_id'):
        cursor.execute("ALTER TABLE purchase_bills ADD COLUMN currency_id INTEGER REFERENCES currencies(id)")
        print("Added currency_id to purchase_bills")
    else:
        print("currency_id already exists in purchase_bills")

    if not column_exists('purchase_bills', 'exchange_rate'):
        cursor.execute("ALTER TABLE purchase_bills ADD COLUMN exchange_rate REAL DEFAULT 1.0")
        print("Added exchange_rate to purchase_bills")
    else:
        print("exchange_rate already exists in purchase_bills")

    # Check and add new fields to transactions table
    if not column_exists('transactions', 'amount'):
        cursor.execute("ALTER TABLE transactions ADD COLUMN amount REAL DEFAULT 0")
        print("Added amount to transactions")
    if not column_exists('transactions', 'payment_mode'):
        cursor.execute("ALTER TABLE transactions ADD COLUMN payment_mode VARCHAR(30) DEFAULT 'Cash'")
        print("Added payment_mode to transactions")
    if not column_exists('transactions', 'invoice_id'):
        cursor.execute("ALTER TABLE transactions ADD COLUMN invoice_id INTEGER")
        print("Added invoice_id to transactions")
    if not column_exists('transactions', 'status'):
        cursor.execute("ALTER TABLE transactions ADD COLUMN status VARCHAR(20) DEFAULT 'Pending'")
        print("Added status to transactions")
    if not column_exists('transactions', 'debit_account'):
        cursor.execute("ALTER TABLE transactions ADD COLUMN debit_account VARCHAR(100)")
        print("Added debit_account to transactions")
    if not column_exists('transactions', 'credit_account'):
        cursor.execute("ALTER TABLE transactions ADD COLUMN credit_account VARCHAR(100)")
        print("Added credit_account to transactions")
    if not column_exists('transactions', 'is_mapped'):
        cursor.execute("ALTER TABLE transactions ADD COLUMN is_mapped BOOLEAN DEFAULT 0")
        print("Added is_mapped to transactions")

    # Commit the changes
    conn.commit()
    print("Database schema updated successfully!")

except sqlite3.OperationalError as e:
    print(f"Error updating database: {e}")

finally:
    conn.close()