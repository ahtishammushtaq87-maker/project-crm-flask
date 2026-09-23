-- ============================================================================
--  Adds is_draft to expense_categories, giving "Draft" its own persistent
--  state distinct from "Pending" on the universal Approval widget.
--
--  Before this column existed, ExpenseCategory had no draft_field wired
--  into ApprovalService.MODULE_CONFIG, so clicking "Set to Draft" on a
--  category just cleared is_approved/is_rejected - identical to "Set to
--  Pending" - and the badge always read back as "Pending". This column
--  lets Draft be tracked and shown separately (its own tab on the Expense
--  Categories page), and a Draft category is now excluded from every
--  category-picking dropdown in the Expense module (Add/Edit Expense's
--  Category field and its Category/Sub-Category tree).
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_expense_category_is_draft.sql
--
--  Safe to run on a database that already has this column: SQLite will
--  report "duplicate column name: is_draft" and skip it.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE expense_categories ADD COLUMN is_draft BOOLEAN DEFAULT 0;

-- Grandfathering: every category that exists right now is left out of
-- Draft (is_draft = 0), so nothing that currently shows up in Add/Edit
-- Expense's dropdown disappears from it after this migration runs.
UPDATE expense_categories SET is_draft = 0 WHERE is_draft IS NOT 0;

COMMIT;

-- ============================================================================
--  Verification — should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('expense_categories') WHERE name = 'is_draft';
