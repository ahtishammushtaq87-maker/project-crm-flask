-- ============================================================================
--  Schema changes for the live (VPS) SQLite database
--
--  Covers everything added in this round of work:
--    1. journal_entries.is_draft        - real storage for "Set to Draft"
--    2. expenses.is_draft               - same, for the Expense approval widget
--    3. fixed_expenses (new table)      - recurring day-based expense templates
--    4. expenses.fixed_expense_id       - links a generated row to its template
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_fixed_expenses_and_draft.sql
--
--  Safe to run on a database that already has some of these: SQLite will
--  report "duplicate column name: ..." for an ALTER that was already applied
--  and skip it. That message is expected — the CREATE statements below use
--  IF NOT EXISTS and are always safe.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- ---------------------------------------------------------------------------
-- 1. Draft flag on journal entries
--    Without this, "Set to Draft" has nowhere to record itself and silently
--    reads back as Pending.
-- ---------------------------------------------------------------------------
ALTER TABLE journal_entries ADD COLUMN is_draft BOOLEAN DEFAULT 0;

-- ---------------------------------------------------------------------------
-- 2. Draft flag on expenses (same reason)
-- ---------------------------------------------------------------------------
ALTER TABLE expenses ADD COLUMN is_draft BOOLEAN DEFAULT 0;

-- ---------------------------------------------------------------------------
-- 3. Fixed (recurring, day-based) expense templates
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fixed_expenses (
    id                INTEGER NOT NULL,
    name              VARCHAR(150) NOT NULL,
    description       TEXT,
    category_id       INTEGER,
    vendor_id         INTEGER,
    mode              VARCHAR(10),      -- 'divide' | 'multiply'
    amount            FLOAT,            -- divide: cycle total; multiply: per-day rate
    days              INTEGER,          -- cycle length in days
    start_date        DATE,
    is_active         BOOLEAN,
    auto_post         BOOLEAN,          -- write each cycle into the Expense book
    cycles_posted     INTEGER,          -- how many cycles are already written
    days_posted       INTEGER,
    paused_on         DATE,             -- date it was last switched off
    accrued_amount    FLOAT,            -- manual mode: accrued but not yet posted
    posted_amount     FLOAT,            -- lifetime total committed to the book
    days_accrued      INTEGER,
    last_accrued_date DATE,
    created_at        DATETIME,
    created_by        INTEGER,
    PRIMARY KEY (id),
    FOREIGN KEY(category_id) REFERENCES expense_categories (id),
    FOREIGN KEY(vendor_id)   REFERENCES vendors (id),
    FOREIGN KEY(created_by)  REFERENCES users (id)
);

-- ---------------------------------------------------------------------------
-- 4. Link a generated expense row back to the template that produced it
--    (drives the Fixed / Stopped badge and lets a stop trim the open cycle)
-- ---------------------------------------------------------------------------
ALTER TABLE expenses ADD COLUMN fixed_expense_id INTEGER REFERENCES fixed_expenses (id);

-- ---------------------------------------------------------------------------
-- Indexes the models declare
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_journal_entries_is_draft    ON journal_entries (is_draft);
CREATE INDEX IF NOT EXISTS ix_expenses_is_draft           ON expenses (is_draft);
CREATE INDEX IF NOT EXISTS ix_expenses_fixed_expense_id   ON expenses (fixed_expense_id);
CREATE INDEX IF NOT EXISTS ix_fixed_expenses_is_active    ON fixed_expenses (is_active);

-- ---------------------------------------------------------------------------
-- Backfill: existing rows must not be left NULL, or they would drop out of
-- every status tab (the tabs are NULL-safe, but 0 keeps the data clean).
-- ---------------------------------------------------------------------------
UPDATE journal_entries SET is_draft = 0 WHERE is_draft IS NULL;
UPDATE expenses        SET is_draft = 0 WHERE is_draft IS NULL;

COMMIT;

-- ============================================================================
--  Verification — every row below should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('journal_entries') WHERE name = 'is_draft';
-- SELECT COUNT(*) FROM pragma_table_info('expenses')        WHERE name = 'is_draft';
-- SELECT COUNT(*) FROM pragma_table_info('expenses')        WHERE name = 'fixed_expense_id';
-- SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name = 'fixed_expenses';
