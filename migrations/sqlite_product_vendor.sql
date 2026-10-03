-- ============================================================================
--  Product -> Vendor link (default / preferred supplier of an item).
--
--  Adds a nullable vendor_id to products, chosen from the searchable Vendor
--  dropdown on Inventory > Add Product / Edit Product. Existing products
--  keep vendor_id = NULL ("No Vendor") until someone edits them.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_product_vendor.sql
--
--  Safe to run on a database that already has this column: SQLite will
--  report "duplicate column name" and skip it.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE products ADD COLUMN vendor_id INTEGER REFERENCES vendors (id);

CREATE INDEX IF NOT EXISTS ix_products_vendor_id ON products (vendor_id);

COMMIT;

-- ============================================================================
--  Verification — should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('products') WHERE name = 'vendor_id';

-- ============================================================================
--  PostgreSQL equivalent
-- ============================================================================
-- ALTER TABLE products ADD COLUMN IF NOT EXISTS vendor_id INTEGER REFERENCES vendors (id);
-- CREATE INDEX IF NOT EXISTS ix_products_vendor_id ON products (vendor_id);
