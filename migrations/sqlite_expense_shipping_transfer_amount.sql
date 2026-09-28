-- ============================================================================
--  Adds expenses.shipping_transfer_amount for "Add this to PO Shipping" on
--  Add/Edit Expense: the amount this expense added to its linked Purchase
--  Bill's shipping charge (0 = not a shipping transfer).
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_expense_shipping_transfer_amount.sql
--
--  Safe to run on a database that already has this column: SQLite will
--  report "duplicate column name: shipping_transfer_amount" and skip it.
-- ============================================================================

ALTER TABLE expenses ADD COLUMN shipping_transfer_amount FLOAT DEFAULT 0;

-- ============================================================================
--  Verification - should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('expenses') WHERE name = 'shipping_transfer_amount';
