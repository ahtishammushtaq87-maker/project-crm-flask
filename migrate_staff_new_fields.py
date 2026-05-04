
import sqlite3
import os

db_path = r'd:\prefex_flask\project_crm_flask\for table\project_crm_flask\instance\crm.db'

def migrate():
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add agreement_letter column to staff table
        cursor.execute("ALTER TABLE staff ADD COLUMN agreement_letter VARCHAR(255)")
        print("Added agreement_letter column to staff table")
    except sqlite3.OperationalError as e:
        print(f"Error adding agreement_letter: {e}")

    try:
        # Add joining_advance column to staff table
        cursor.execute("ALTER TABLE staff ADD COLUMN joining_advance FLOAT DEFAULT 0")
        print("Added joining_advance column to staff table")
    except sqlite3.OperationalError as e:
        print(f"Error adding joining_advance: {e}")

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == '__main__':
    migrate()
