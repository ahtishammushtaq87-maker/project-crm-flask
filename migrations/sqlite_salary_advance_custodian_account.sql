-- ============================================================================
--  Pay a Salary Advance out of a custodian account.
--
--  Selecting a Custodian Account on Record Advance now posts a 'credit'
--  (money out) row against that account - the same direction and mechanism an
--  Expense uses - so the advance actually reduces that account's balance.
--  Deleting the advance removes the movement and returns the money.
--
--    salary_advances.expense_account_id
--        which custodian account the cash was paid from (NULL = none, which
--        is how every existing advance stays: no account touched).
--
--    expense_account_transactions.salary_advance_id
--        back-link on the credit row, set instead of expense_id when
--        transaction_type = 'salary_advance', so a delete can find and
--        reverse exactly its own movement.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_salary_advance_custodian_account.sql
--
--  Safe to run on a database that already has these columns: SQLite will
--  report "duplicate column name" and skip it.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE salary_advances ADD COLUMN expense_account_id INTEGER
    REFERENCES expense_accounts (id);

ALTER TABLE expense_account_transactions ADD COLUMN salary_advance_id INTEGER
    REFERENCES salary_advances (id);

CREATE INDEX IF NOT EXISTS ix_salary_advances_expense_account_id
    ON salary_advances (expense_account_id);

CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_salary_advance_id
    ON expense_account_transactions (salary_advance_id);

COMMIT;

-- ============================================================================
--  Verification — each should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('salary_advances')
--   WHERE name = 'expense_account_id';
-- SELECT COUNT(*) FROM pragma_table_info('expense_account_transactions')
--   WHERE name = 'salary_advance_id';
