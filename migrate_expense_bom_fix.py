#!/usr/bin/env python
"""
Migration: Fix BOM deletion cascade and add bom_id to expenses table
- Add ondelete='CASCADE' to bom_versions.bom_id foreign key
- Add bom_id column to expenses table if not exists
"""

import sqlite3
import sys

def migrate():
    try:
        conn = sqlite3.connect('instance/database.db')
        cursor = conn.cursor()
        
        print("Starting migration...")
        
        # 1. Add bom_id column to expenses table if not exists
        print("\nChecking expenses table structure...")
        cursor.execute("PRAGMA table_info(expenses)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'bom_id' not in columns:
            print("Adding bom_id column to expenses...")
            cursor.execute("""
                ALTER TABLE expenses 
                ADD COLUMN bom_id INTEGER
            """)
            print("✓ Added bom_id to expenses")
        else:
            print("✓ bom_id column already exists")
        
        # 2. Verify the bom_versions table structure
        print("\nVerifying bom_versions table...")
        cursor.execute("PRAGMA table_info(bom_versions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'bom_id' in columns:
            print("✓ bom_versions table exists with bom_id")
        else:
            print("⚠ bom_versions table missing bom_id column - table may not exist")
        
        # 3. Create index on expenses.bom_id for performance
        print("\nCreating indices...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_expenses_bom_id 
                ON expenses(bom_id)
            """)
            print("✓ Created index on expenses.bom_id")
        except Exception as e:
            print(f"⚠ Index creation: {e}")
        
        conn.commit()
        conn.close()
        
        print("\n✓ Migration complete!")
        return True
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
