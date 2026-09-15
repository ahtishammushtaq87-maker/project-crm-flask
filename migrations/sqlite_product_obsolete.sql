-- ============================================================================
--  Obsolete Product flag (admin-only lifecycle state).
--
--  Marking a product Obsolete hides it from "pick a product" dropdowns used
--  to create NEW records across Sales, Quotations, Purchase, BOM,
--  Manufacturing Orders, Production Targets/Logs, Expenses, Tools, and
--  Product Development. It does NOT delete the product, does not touch
--  stock/cost, and every EXISTING record that already references it keeps
--  displaying and editing normally (each relevant dropdown defensively
--  re-includes the linked product, labelled "(Obsolete)", if it's not in
--  the base non-obsolete list).
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_product_obsolete.sql
--
--  Safe to run on a database that already has these columns: SQLite will
--  report "duplicate column name" and skip it.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE products ADD COLUMN is_obsolete BOOLEAN DEFAULT 0;
ALTER TABLE products ADD COLUMN obsoleted_at DATETIME;
ALTER TABLE products ADD COLUMN obsoleted_by INTEGER REFERENCES users (id);

-- Every product that exists right now has never been marked obsolete, so it
-- keeps appearing everywhere it already does.
UPDATE products SET is_obsolete = 0 WHERE is_obsolete IS NULL;

CREATE INDEX IF NOT EXISTS ix_products_is_obsolete ON products (is_obsolete);

COMMIT;

-- ============================================================================
--  Verification — should print 3
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('products')
--   WHERE name IN ('is_obsolete', 'obsoleted_at', 'obsoleted_by');
