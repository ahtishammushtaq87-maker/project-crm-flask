-- ============================================================================
--  LIVE DATABASE (SQLite) — everything added for:
--    • Finance > Journal Entries (between Expense accounts)
--    • Vendor / Customer on journal lines
--    • Purchase bill payments paid from a bank / cash account
--    • Vendor advances paid from a bank / cash account
--
--  The app also adds these automatically on startup; run this to apply them
--  by hand. Back up first:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_finance_journal_entries.sql
--
--  Safe to re-run: CREATE ... IF NOT EXISTS is always safe; an ALTER that
--  was already applied fails with "duplicate column name: ..." — expected,
--  just ignore it (run each ALTER on its own if your client stops on error).
-- ============================================================================

-- 1. Journal entry header ----------------------------------------------------
CREATE TABLE IF NOT EXISTS finance_journal_entries (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    number                 INTEGER NOT NULL UNIQUE,
    date                   DATE NOT NULL,
    reference              VARCHAR(120),
    description            TEXT,
    status                 VARCHAR(20) NOT NULL DEFAULT 'approved',
    rejection_reason       TEXT,
    approved_by            INTEGER REFERENCES users(id),
    approved_at            DATETIME,
    is_recurring           BOOLEAN DEFAULT 0,
    recurring_interval     INTEGER,
    recurring_unit         VARCHAR(10),
    recurring_cycles       INTEGER DEFAULT 0,
    recurring_cycles_done  INTEGER DEFAULT 0,
    last_recurring_date    DATE,
    recurring_parent_id    INTEGER REFERENCES finance_journal_entries(id),
    created_by             INTEGER REFERENCES users(id),
    created_at             DATETIME,
    updated_at             DATETIME
);
CREATE INDEX IF NOT EXISTS ix_finance_journal_entries_number              ON finance_journal_entries (number);
CREATE INDEX IF NOT EXISTS ix_finance_journal_entries_date                ON finance_journal_entries (date);
CREATE INDEX IF NOT EXISTS ix_finance_journal_entries_status              ON finance_journal_entries (status);
CREATE INDEX IF NOT EXISTS ix_finance_journal_entries_is_recurring        ON finance_journal_entries (is_recurring);
CREATE INDEX IF NOT EXISTS ix_finance_journal_entries_recurring_parent_id ON finance_journal_entries (recurring_parent_id);

-- 2. New columns on account transactions -------------------------------------
ALTER TABLE expense_account_transactions ADD COLUMN journal_entry_id  INTEGER REFERENCES finance_journal_entries(id);
ALTER TABLE expense_account_transactions ADD COLUMN vendor_id         INTEGER REFERENCES vendors(id);
ALTER TABLE expense_account_transactions ADD COLUMN bill_payment_id   INTEGER REFERENCES bill_payments(id);
ALTER TABLE expense_account_transactions ADD COLUMN vendor_advance_id INTEGER REFERENCES vendor_advances(id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_journal_entry_id  ON expense_account_transactions (journal_entry_id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_vendor_id         ON expense_account_transactions (vendor_id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_bill_payment_id   ON expense_account_transactions (bill_payment_id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_vendor_advance_id ON expense_account_transactions (vendor_advance_id);

-- 3. "Paid from account" on bill payments and vendor advances ----------------
ALTER TABLE bill_payments   ADD COLUMN expense_account_id INTEGER REFERENCES expense_accounts(id);
ALTER TABLE vendor_advances ADD COLUMN expense_account_id INTEGER REFERENCES expense_accounts(id);
CREATE INDEX IF NOT EXISTS ix_bill_payments_expense_account_id   ON bill_payments (expense_account_id);
CREATE INDEX IF NOT EXISTS ix_vendor_advances_expense_account_id ON vendor_advances (expense_account_id);
