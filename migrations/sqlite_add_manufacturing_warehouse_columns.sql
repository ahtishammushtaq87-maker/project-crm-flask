-- Migration: add warehouse columns for manufacturing BOM and orders (SQLite)
-- Run these statements against your SQLite DB (e.g. using sqlite3 CLI or a DB tool).
-- NOTE: SQLite does not support adding foreign key constraints via ALTER TABLE for existing tables.
-- These statements add nullable integer columns. If you need enforced FK constraints, recreate tables.

PRAGMA foreign_keys=OFF;

BEGIN TRANSACTION;

ALTER TABLE bom_items ADD COLUMN warehouse_id INTEGER;
ALTER TABLE manufacturing_orders ADD COLUMN finished_warehouse_id INTEGER;
ALTER TABLE manufacturing_order_items ADD COLUMN warehouse_id INTEGER;

COMMIT;

PRAGMA foreign_keys=ON;

-- Optional: verify columns were added:
-- PRAGMA table_info('bom_items');
-- PRAGMA table_info('manufacturing_orders');
-- PRAGMA table_info('manufacturing_order_items');

-- After running this migration, run the Flask app and exercise the manufacturing flows.
-- If you use Flask-Migrate/Alembic, create a proper alembic revision that adds these columns instead.
