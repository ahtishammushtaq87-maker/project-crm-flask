-- ============================================================================
--  Adds the 6th per-category option flag: allow_pd_shift, for
--  "Shift Expense to PD Project" on Add/Edit Expense.
--
--  Follow-up to sqlite_expense_category_allow_monthly_divided.sql.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_expense_category_allow_pd_shift.sql
--
--  Safe to run on a database that already has this column: SQLite will
--  report "duplicate column name: allow_pd_shift" and skip it.
--
--  No grandfathering: existing categories start with this OFF. Turning it
--  on for every category would make admins pick an option on categories
--  that are meant to be plain expenses. Tick it on the parent categories
--  that should offer it. The "Shift to PD Project" button on the Expenses
--  list keeps working for every expense, whatever this flag says.
-- ============================================================================

ALTER TABLE expense_categories ADD COLUMN allow_pd_shift BOOLEAN DEFAULT 0;

-- ============================================================================
--  Verification - should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('expense_categories') WHERE name = 'allow_pd_shift';
