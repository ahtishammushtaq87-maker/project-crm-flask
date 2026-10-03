-- ============================================================================
--  Cost history per warehouse.
--
--  cost_price_history.warehouse_id:
--    NULL = the item's normal cost (products.cost_price) changed
--    set  = that warehouse's own cost (product_warehouse_stock.cost_price)
--           changed
--  Rows are now written automatically for EVERY cost change (Edit Item,
--  purchase, production, manufacturing, transfers, tools, expenses,
--  approvals, bulk upload) by app/services/cost_history.py.
--
--  Existing rows keep warehouse_id = NULL (they were all item-cost rows).
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_cost_history_warehouse.sql
--
--  Safe to run on a database that already has the column: SQLite will
--  report "duplicate column name" and skip it.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE cost_price_history ADD COLUMN warehouse_id INTEGER REFERENCES warehouses (id);

CREATE INDEX IF NOT EXISTS ix_cost_price_history_warehouse_id ON cost_price_history (warehouse_id);

COMMIT;

-- ============================================================================
--  Verification - should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('cost_price_history') WHERE name = 'warehouse_id';

-- ============================================================================
--  PostgreSQL equivalent
-- ============================================================================
-- ALTER TABLE cost_price_history ADD COLUMN IF NOT EXISTS warehouse_id INTEGER REFERENCES warehouses (id);
-- CREATE INDEX IF NOT EXISTS ix_cost_price_history_warehouse_id ON cost_price_history (warehouse_id);
