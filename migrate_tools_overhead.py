
import sqlite3
import os

def migrate():
    db_path = r'd:\prefex_flask\project_crm_flask\for table\project_crm_flask\instance\database.db'
    if not os.path.exists(db_path):
        db_path = r'd:\prefex_flask\project_crm_flask\for table\project_crm_flask\database.db' # Fallback
        
    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Adding BOM Overhead columns to tool_receiving...")
        # Check if columns exist first
        cursor.execute("PRAGMA table_info(tool_receiving)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_bom_overhead' not in columns:
            cursor.execute("ALTER TABLE tool_receiving ADD COLUMN is_bom_overhead BOOLEAN DEFAULT 0")
            print("Added is_bom_overhead")
        
        if 'overhead_type' not in columns:
            cursor.execute("ALTER TABLE tool_receiving ADD COLUMN overhead_type VARCHAR(20)")
            print("Added overhead_type")
            
        if 'allocated_ids' not in columns:
            cursor.execute("ALTER TABLE tool_receiving ADD COLUMN allocated_ids TEXT")
            print("Added allocated_ids")

        conn.commit()
        print("Migration successful!")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
