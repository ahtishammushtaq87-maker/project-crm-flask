"""Add the WhatsApp-share token columns to `packing_slips`.

Same access_token/token_expiry pattern already used by Sale/PurchaseBill/
Quotation, so a Packing Slip can be shared as a public, no-login-required PDF
link. Existing rows get NULL for both (no token issued yet — one is generated
lazily the first time someone clicks Share).

Safe to run repeatedly: each column is added only if it is missing, so an
already-migrated database is left untouched. A timestamped backup of the
SQLite file is taken first.

    python migrate_packing_slip_share_token.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')

COLUMNS = [
    ('access_token', 'VARCHAR(100)'),
    ('token_expiry', 'DATETIME'),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f'Database not found at {DB_PATH} — nothing to migrate.')
        return

    backup = f'{DB_PATH}.bak-before-packing-slip-share-token-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup written to {backup}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = {row[1] for row in cur.execute('PRAGMA table_info(packing_slips)')}
    added = 0
    for name, sql_type in COLUMNS:
        if name in existing:
            print(f'  = {name} already present — skipped')
            continue
        cur.execute(f'ALTER TABLE packing_slips ADD COLUMN {name} {sql_type}')
        print(f'  + {name} added')
        added += 1

    # access_token must stay unique — add the index the model declares.
    try:
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_packing_slips_access_token '
                    'ON packing_slips (access_token)')
    except sqlite3.OperationalError as e:
        print(f'  (index not created: {e})')

    conn.commit()
    conn.close()
    print(f'Done — {added} column(s) added.')


if __name__ == '__main__':
    main()
