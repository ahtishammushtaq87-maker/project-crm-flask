-- ============================================================================
--  Schema change for the live (VPS) SQLite database — receive a sales invoice
--  payment into a bank / cash account
--
--  Adds:  payments.expense_account_id
--         expense_account_transactions.sale_payment_id
--         expense_account_transactions.customer_advance_id
--
--  What it is: Record Payment, Edit Payment and Universal Pay can now pick the
--  account (Expense > Manage Accounts) the customer's money was received into.
--  The payment then posts a DEBIT (money in) row on that account, linked by
--  sale_payment_id; the Universal Pay leftover that becomes a customer advance
--  gets its own row, linked by customer_advance_id. Every column is nullable,
--  so existing payments are untouched (they simply have no account).
--
--  The app also adds these columns by itself on startup (auto-migration), so
--  running this file is only needed if you prefer to apply it by hand first.
--  Back up first:
--      cp instance/database.db instance/database.db.bak-$(date +%F)
--      sqlite3 instance/database.db < migrations/sqlite_sale_payment_receipt_account.sql
--
--  Re-running stops at "duplicate column name" — harmless, it just means the
--  column is already there.
-- ============================================================================

BEGIN TRANSACTION;

ALTER TABLE payments ADD COLUMN expense_account_id INTEGER REFERENCES expense_accounts(id);
ALTER TABLE expense_account_transactions ADD COLUMN sale_payment_id INTEGER REFERENCES payments(id);
ALTER TABLE expense_account_transactions ADD COLUMN customer_advance_id INTEGER REFERENCES customer_advances(id);

CREATE INDEX IF NOT EXISTS ix_payments_expense_account_id ON payments (expense_account_id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_sale_payment_id ON expense_account_transactions (sale_payment_id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_customer_advance_id ON expense_account_transactions (customer_advance_id);

COMMIT;

-- ============================================================================
--  PostgreSQL equivalent
-- ============================================================================
-- ALTER TABLE payments ADD COLUMN IF NOT EXISTS expense_account_id INTEGER REFERENCES expense_accounts(id);
-- ALTER TABLE expense_account_transactions ADD COLUMN IF NOT EXISTS sale_payment_id INTEGER REFERENCES payments(id);
-- ALTER TABLE expense_account_transactions ADD COLUMN IF NOT EXISTS customer_advance_id INTEGER REFERENCES customer_advances(id);
-- CREATE INDEX IF NOT EXISTS ix_payments_expense_account_id ON payments (expense_account_id);
-- CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_sale_payment_id ON expense_account_transactions (sale_payment_id);
-- CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_customer_advance_id ON expense_account_transactions (customer_advance_id);

-- ============================================================================
--  Verification
-- ============================================================================
-- Should print 1 each:
-- SELECT COUNT(*) FROM pragma_table_info('payments') WHERE name = 'expense_account_id';
-- SELECT COUNT(*) FROM pragma_table_info('expense_account_transactions') WHERE name = 'sale_payment_id';
-- SELECT COUNT(*) FROM pragma_table_info('expense_account_transactions') WHERE name = 'customer_advance_id';
--
-- Payments received into an account, with their account rows:
-- SELECT p.payment_number, p.amount, a.name, t.entry_type, t.amount, t.is_approved
--   FROM payments p
--   JOIN expense_accounts a ON a.id = p.expense_account_id
--   LEFT JOIN expense_account_transactions t ON t.sale_payment_id = p.id
--  ORDER BY p.id DESC LIMIT 20;
