-- ============================================================================
--  LIVE DATABASE (PostgreSQL) — same changes as sqlite_finance_journal_entries.sql.
--  Fully re-runnable (IF NOT EXISTS everywhere). Back up first:
--      pg_dump -Fc yourdb > yourdb-$(date +%F).dump
--      psql yourdb -f postgres_finance_journal_entries.sql
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS finance_journal_entries (
    id                     SERIAL PRIMARY KEY,
    number                 INTEGER NOT NULL UNIQUE,
    date                   DATE NOT NULL,
    reference              VARCHAR(120),
    description            TEXT,
    status                 VARCHAR(20) NOT NULL DEFAULT 'approved',
    rejection_reason       TEXT,
    approved_by            INTEGER REFERENCES users(id),
    approved_at            TIMESTAMP,
    is_recurring           BOOLEAN DEFAULT FALSE,
    recurring_interval     INTEGER,
    recurring_unit         VARCHAR(10),
    recurring_cycles       INTEGER DEFAULT 0,
    recurring_cycles_done  INTEGER DEFAULT 0,
    last_recurring_date    DATE,
    recurring_parent_id    INTEGER REFERENCES finance_journal_entries(id),
    created_by             INTEGER REFERENCES users(id),
    created_at             TIMESTAMP,
    updated_at             TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_finance_journal_entries_number              ON finance_journal_entries (number);
CREATE INDEX IF NOT EXISTS ix_finance_journal_entries_date                ON finance_journal_entries (date);
CREATE INDEX IF NOT EXISTS ix_finance_journal_entries_status              ON finance_journal_entries (status);
CREATE INDEX IF NOT EXISTS ix_finance_journal_entries_is_recurring        ON finance_journal_entries (is_recurring);
CREATE INDEX IF NOT EXISTS ix_finance_journal_entries_recurring_parent_id ON finance_journal_entries (recurring_parent_id);

ALTER TABLE expense_account_transactions ADD COLUMN IF NOT EXISTS journal_entry_id  INTEGER REFERENCES finance_journal_entries(id);
ALTER TABLE expense_account_transactions ADD COLUMN IF NOT EXISTS vendor_id         INTEGER REFERENCES vendors(id);
ALTER TABLE expense_account_transactions ADD COLUMN IF NOT EXISTS bill_payment_id   INTEGER REFERENCES bill_payments(id);
ALTER TABLE expense_account_transactions ADD COLUMN IF NOT EXISTS vendor_advance_id INTEGER REFERENCES vendor_advances(id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_journal_entry_id  ON expense_account_transactions (journal_entry_id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_vendor_id         ON expense_account_transactions (vendor_id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_bill_payment_id   ON expense_account_transactions (bill_payment_id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_vendor_advance_id ON expense_account_transactions (vendor_advance_id);

ALTER TABLE bill_payments   ADD COLUMN IF NOT EXISTS expense_account_id INTEGER REFERENCES expense_accounts(id);
ALTER TABLE vendor_advances ADD COLUMN IF NOT EXISTS expense_account_id INTEGER REFERENCES expense_accounts(id);
CREATE INDEX IF NOT EXISTS ix_bill_payments_expense_account_id   ON bill_payments (expense_account_id);
CREATE INDEX IF NOT EXISTS ix_vendor_advances_expense_account_id ON vendor_advances (expense_account_id);

COMMIT;
