-- ============================================================================
--  Adds the 5th per-category option flag: allow_monthly_divided, for
--  "Divide Expense Across Entire Month" on Add/Edit Expense.
--
--  Follow-up to sqlite_expense_category_hierarchy_and_options.sql (parent_id,
--  allow_invoice_payment, allow_purchase_payment, allow_inventory_shift,
--  allow_bom_overhead) - run that one first if it hasn't been applied yet.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_expense_category_allow_monthly_divided.sql
--
--  Safe to run on a database that already has this column: SQLite will
--  report "duplicate column name: allow_monthly_divided" and skip it.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE expense_categories ADD COLUMN allow_monthly_divided BOOLEAN DEFAULT 0;

-- Grandfathering, same reasoning as the other four flags: every category
-- that exists right now keeps full access (Monthly Division included), so
-- nothing that currently works today silently breaks. Run only once.
UPDATE expense_categories SET allow_monthly_divided = 1 WHERE allow_monthly_divided IS NOT 1;

COMMIT;

-- ============================================================================
--  Verification — should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('expense_categories') WHERE name = 'allow_monthly_divided';
