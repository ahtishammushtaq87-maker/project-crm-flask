-- ============================================================================
--  Adds sku_prefix ("SKU Structure") to product_categories.
--
--  Items created in a category with a structure get their SKU generated
--  automatically: structure 1010 -> 1010001, 1010002, ...; if items with that
--  structure already exist, the next number after the highest one is used.
--
--  The app's startup auto-migration also adds this column, so running this
--  by hand is only needed if auto-migration is disabled.
--      sqlite3 database.db < sqlite_product_category_sku_prefix.sql
--
--  Safe to run on a database that already has this column: SQLite will
--  report "duplicate column name: sku_prefix" and skip it.
-- ============================================================================

ALTER TABLE product_categories ADD COLUMN sku_prefix VARCHAR(20);

-- ============================================================================
--  Verification — should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('product_categories') WHERE name = 'sku_prefix';
