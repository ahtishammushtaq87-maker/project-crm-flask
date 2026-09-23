-- ============================================================================
--  Adds shipping_image_path to purchase_bills, so a shipping receipt/proof
--  image (e.g. courier receipt, freight invoice) can be attached alongside
--  the shipping charge on a Purchase Bill, previewed on the bill detail page
--  the same way bill_image_path already is.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_purchase_bill_shipping_image.sql
--
--  Safe to run again later: the app's own startup auto-migrator already
--  adds this column automatically (PurchaseBill is registered in its table
--  list), so this file is only needed if you want it applied immediately
--  without waiting for a restart. SQLite will report "duplicate column
--  name: shipping_image_path" and skip it if already applied.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE purchase_bills ADD COLUMN shipping_image_path VARCHAR(255);

COMMIT;

-- ============================================================================
--  Verification — should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('purchase_bills') WHERE name = 'shipping_image_path';
