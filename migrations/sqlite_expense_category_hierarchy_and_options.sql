-- ============================================================================
--  Schema changes for the live (VPS) SQLite database
--
--  Covers everything added for category-restricted Expense options:
--    1. expense_categories.parent_id              - one level of sub-categories
--    2. expense_categories.allow_invoice_payment   - per-category option flags
--    3. expense_categories.allow_purchase_payment
--    4. expense_categories.allow_inventory_shift
--    5. expense_categories.allow_bom_overhead
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_expense_category_hierarchy_and_options.sql
--
--  Safe to run on a database that already has some of these: SQLite will
--  report "duplicate column name: ..." for an ALTER that was already applied
--  and skip it. That message is expected.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- ---------------------------------------------------------------------------
-- 1. Parent category (NULL = main/top-level category; set = sub-category of
--    that main category). Only one level deep - a sub-category's own
--    subcategories relationship is simply never populated by the UI.
-- ---------------------------------------------------------------------------
ALTER TABLE expense_categories ADD COLUMN parent_id INTEGER REFERENCES expense_categories (id);

-- ---------------------------------------------------------------------------
-- 2-5. Per-category option flags - which special Add/Edit Expense behaviors
--      this category is allowed to use. Each ALTER defaults new/existing
--      rows to 0 (off); the backfill below then turns all four ON for every
--      category that already existed before this migration, so nothing
--      that currently works today silently breaks. Categories created AFTER
--      this migration start with all four OFF, so an admin consciously
--      opts each one in via Edit Category.
-- ---------------------------------------------------------------------------
ALTER TABLE expense_categories ADD COLUMN allow_invoice_payment  BOOLEAN DEFAULT 0;
ALTER TABLE expense_categories ADD COLUMN allow_purchase_payment BOOLEAN DEFAULT 0;
ALTER TABLE expense_categories ADD COLUMN allow_inventory_shift  BOOLEAN DEFAULT 0;
ALTER TABLE expense_categories ADD COLUMN allow_bom_overhead     BOOLEAN DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_expense_categories_parent_id ON expense_categories (parent_id);

-- ---------------------------------------------------------------------------
-- Backfill / grandfathering: every category that exists right now keeps
-- full access to all four options (matches today's behavior, where every
-- category can use any of them). Run this UPDATE only once, right after
-- the ALTERs above - re-running it later would also re-enable everything
-- for categories an admin had since deliberately restricted.
-- ---------------------------------------------------------------------------
UPDATE expense_categories
SET allow_invoice_payment = 1, allow_purchase_payment = 1, allow_inventory_shift = 1, allow_bom_overhead = 1
WHERE allow_invoice_payment IS NOT 1 OR allow_purchase_payment IS NOT 1
   OR allow_inventory_shift IS NOT 1 OR allow_bom_overhead IS NOT 1;

COMMIT;

-- ============================================================================
--  Verification — every row below should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('expense_categories') WHERE name = 'parent_id';
-- SELECT COUNT(*) FROM pragma_table_info('expense_categories') WHERE name = 'allow_invoice_payment';
-- SELECT COUNT(*) FROM pragma_table_info('expense_categories') WHERE name = 'allow_purchase_payment';
-- SELECT COUNT(*) FROM pragma_table_info('expense_categories') WHERE name = 'allow_inventory_shift';
-- SELECT COUNT(*) FROM pragma_table_info('expense_categories') WHERE name = 'allow_bom_overhead';
