"""
Migration: Full task group migration — safe to run multiple times, zero data loss.

Steps:
  1. Add task_group_name column to tasks (if not exists)
  2. Add linked_invoice_id column to tasks (if not exists)
  3. Create task_groups table (if not exists)

Uses Flask app context so the DB path is resolved correctly.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
import sqlite3

app = create_app()

with app.app_context():
    # ── Resolve the actual SQLite DB file path ────────────────────────────────
    db_uri = db.engine.url
    db_path = str(db_uri).replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), db_path)

    print(f"\n✔  DB path: {db_path}\n")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    changes = []

    # ── STEP 1: Add task_group_name column to tasks ───────────────────────────
    cursor.execute("PRAGMA table_info(tasks)")
    existing_task_cols = [row[1] for row in cursor.fetchall()]
    print(f"[tasks] Existing columns: {existing_task_cols}")

    if 'task_group_name' not in existing_task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN task_group_name VARCHAR(100)")
        changes.append('tasks.task_group_name')
        print("  + Added column: task_group_name")
    else:
        print("  - Already exists: task_group_name (skipped)")

    # ── STEP 2: Add linked_invoice_id column to tasks ─────────────────────────
    if 'linked_invoice_id' not in existing_task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN linked_invoice_id INTEGER REFERENCES sales(id)")
        changes.append('tasks.linked_invoice_id')
        print("  + Added column: linked_invoice_id")
    else:
        print("  - Already exists: linked_invoice_id (skipped)")

    # ── STEP 3: Create task_groups table ──────────────────────────────────────
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_groups'")
    table_exists = cursor.fetchone()

    if not table_exists:
        cursor.execute("""
            CREATE TABLE task_groups (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       VARCHAR(100) NOT NULL UNIQUE,
                created_at DATETIME DEFAULT (datetime('now'))
            )
        """)
        changes.append('task_groups (new table)')
        print("\n  + Created table: task_groups")
    else:
        print("\n  - Already exists: task_groups table (skipped)")

    # ── Commit & close ────────────────────────────────────────────────────────
    conn.commit()
    conn.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "─" * 50)
    if changes:
        print(f"✅  Migration complete. Changes applied:")
        for c in changes:
            print(f"     • {c}")
    else:
        print("✅  Migration complete. Database already up to date — no changes needed.")
    print("─" * 50 + "\n")
