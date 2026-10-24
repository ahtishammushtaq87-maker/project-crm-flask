"""One-off repair for the Product Funnel tables on SQLite.

The funnel tables were created with PostgreSQL DDL (`id SERIAL PRIMARY KEY`), which
SQLite accepts but does not auto-number, so rows got NULL ids. This rebuilds every
funnel table with a proper `id INTEGER PRIMARY KEY`, keeping existing rows.
Safe to run more than once, including after a partially applied manual fix.

Usage (from the project folder):  python3 fix_pd_funnel_ids.py [path/to/database.db]
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'database.db')

# Parent tables first so children can be recreated after them
TABLES = {
    'pd_candidates': """CREATE TABLE pd_candidates (
        id INTEGER NOT NULL PRIMARY KEY,
        candidate_code VARCHAR(50) NOT NULL UNIQUE,
        oem_part_number VARCHAR(100) NOT NULL,
        product_name VARCHAR(200) NOT NULL,
        application VARCHAR(255),
        product_category_id INTEGER REFERENCES product_categories (id),
        annual_demand FLOAT, target_price FLOAT, est_unit_cost FLOAT,
        owner_staff_id INTEGER REFERENCES staff (id),
        g1_lead_staff_id INTEGER REFERENCES staff (id),
        g1_target_date DATE, next_evidence VARCHAR(255), notes TEXT,
        status VARCHAR(30),
        project_id INTEGER REFERENCES pd_projects (id),
        created_by INTEGER REFERENCES users (id),
        created_at DATETIME, updated_at DATETIME)""",
    'pd_feasibility_reviews': """CREATE TABLE pd_feasibility_reviews (
        id INTEGER NOT NULL PRIMARY KEY,
        candidate_id INTEGER NOT NULL REFERENCES pd_candidates (id),
        discipline VARCHAR(20) NOT NULL,
        reviewer_staff_id INTEGER REFERENCES staff (id),
        evidence_reference VARCHAR(255), finding TEXT, verdict VARCHAR(20),
        is_current BOOLEAN, review_date DATE, valid_until DATE,
        created_by INTEGER REFERENCES users (id), created_at DATETIME)""",
    'pd_stage_tasks': """CREATE TABLE pd_stage_tasks (
        id INTEGER NOT NULL PRIMARY KEY,
        candidate_id INTEGER REFERENCES pd_candidates (id),
        project_id INTEGER REFERENCES pd_projects (id),
        stage VARCHAR(10), deliverable VARCHAR(255) NOT NULL,
        primary_staff_id INTEGER REFERENCES staff (id),
        due_date DATE, status VARCHAR(20), accepted BOOLEAN,
        evidence_reference VARCHAR(255), created_at DATETIME, updated_at DATETIME)""",
    'pd_task_members': """CREATE TABLE pd_task_members (
        id INTEGER NOT NULL PRIMARY KEY,
        task_id INTEGER NOT NULL REFERENCES pd_stage_tasks (id),
        staff_id INTEGER NOT NULL REFERENCES staff (id),
        role VARCHAR(100))""",
    'pd_gate_reviews': """CREATE TABLE pd_gate_reviews (
        id INTEGER NOT NULL PRIMARY KEY,
        gate VARCHAR(10) NOT NULL,
        candidate_id INTEGER REFERENCES pd_candidates (id),
        project_id INTEGER REFERENCES pd_projects (id),
        decision VARCHAR(20) NOT NULL,
        approver_staff_id INTEGER REFERENCES staff (id),
        decision_date DATE, evidence_reference VARCHAR(255), approved_cap FLOAT, remarks TEXT,
        created_by INTEGER REFERENCES users (id), created_at DATETIME)""",
}
INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_pd_candidates_oem_part_number ON pd_candidates (oem_part_number)",
    "CREATE INDEX IF NOT EXISTS ix_pd_candidates_status ON pd_candidates (status)",
    "CREATE INDEX IF NOT EXISTS ix_pd_feasibility_reviews_candidate_id ON pd_feasibility_reviews (candidate_id)",
    "CREATE INDEX IF NOT EXISTS ix_pd_stage_tasks_candidate_id ON pd_stage_tasks (candidate_id)",
    "CREATE INDEX IF NOT EXISTS ix_pd_task_members_task_id ON pd_task_members (task_id)",
    "CREATE INDEX IF NOT EXISTS ix_pd_gate_reviews_candidate_id ON pd_gate_reviews (candidate_id)",
]


def tables(con):
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def columns(con, table):
    return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]


def id_is_proper(con, table):
    for _, name, ctype, _, _, pk in con.execute(f'PRAGMA table_info("{table}")'):
        if name == 'id':
            return ctype.upper() == 'INTEGER' and pk == 1
    return False


def main():
    if not os.path.exists(DB):
        sys.exit(f'Database not found: {DB}')
    backup = f"{DB}.bak-funnel-fix-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(DB, backup)
    print(f'Backup: {backup}')

    con = sqlite3.connect(DB)
    con.isolation_level = None
    con.execute('PRAGMA foreign_keys=OFF')
    con.execute('BEGIN')
    try:
        existing = tables(con)
        old_sources = {}  # table -> list of old tables to copy rows from
        # Leftover from the earlier manual attempt
        if 'pd_candidates_broken' in existing:
            old_sources.setdefault('pd_candidates', []).append('pd_candidates_broken')

        for name, ddl in TABLES.items():
            if name in existing and not id_is_proper(con, name):
                old = f'{name}__old'
                con.execute(f'DROP TABLE IF EXISTS "{old}"')
                con.execute(f'ALTER TABLE "{name}" RENAME TO "{old}"')
                old_sources.setdefault(name, []).append(old)
                print(f'{name}: bad id column, rebuilding')
            if name not in tables(con):
                con.execute(ddl)
                print(f'{name}: created')
            else:
                print(f'{name}: already correct')

        for name, olds in old_sources.items():
            new_cols = columns(con, name)
            for old in olds:
                cols = [c for c in columns(con, old) if c in new_cols and c != 'id']
                col_list = ', '.join(cols)
                # Skip orphan rows (e.g. a NULL candidate_id left by the broken ids)
                required = [r[1] for r in con.execute(f'PRAGMA table_info("{name}")')
                            if r[3] and r[1] != 'id' and r[1] in cols]
                conds = [f'{c} IS NOT NULL' for c in required]
                if name == 'pd_candidates':
                    conds.append('candidate_code NOT IN (SELECT candidate_code FROM pd_candidates)')
                where = (' WHERE ' + ' AND '.join(conds)) if conds else ''
                order = ' ORDER BY created_at' if 'created_at' in cols else ''
                n = con.execute(f'INSERT INTO "{name}" ({col_list}) SELECT {col_list} FROM "{old}"{where}{order}').rowcount
                print(f'{name}: copied {n} row(s) from {old}')
                con.execute(f'DROP TABLE "{old}"')

        for sql in INDEXES:
            con.execute(sql)
        con.execute('COMMIT')
    except Exception:
        con.execute('ROLLBACK')
        print('Failed; nothing changed. Backup kept at', backup)
        raise

    print('\nCandidates now:')
    for row in con.execute('SELECT id, candidate_code, status FROM pd_candidates ORDER BY id'):
        print('  ', row)
    con.close()
    print('Done. Restart the app (gunicorn).')


if __name__ == '__main__':
    main()
