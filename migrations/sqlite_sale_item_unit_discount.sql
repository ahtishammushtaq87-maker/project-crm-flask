-- ============================================================================
--  Schema change for the live (VPS) SQLite database — per-unit item discount
--
--  Adds:  sale_items.unit_discount
--
--  What it is: the discount typed against an invoice line, expressed PER UNIT.
--  The existing sale_items.discount column keeps its meaning — the whole-line
--  figure (unit_discount x quantity) — so invoice totals, returns, reports and
--  the Profit & Loss all keep reading exactly what they read before.
--
--  Run it AFTER sqlite_fixed_expenses_and_draft.sql. Back up first:
--      cp instance/database.db instance/database.db.bak-$(date +%F)
--      sqlite3 instance/database.db < migrations/sqlite_sale_item_unit_discount.sql
--
--  Re-running stops at "duplicate column name: unit_discount" — harmless,
--  it just means the column is already there.
-- ============================================================================

BEGIN TRANSACTION;

ALTER TABLE sale_items ADD COLUMN unit_discount FLOAT DEFAULT 0;

-- Backfill: existing lines only carry the whole-line discount, so derive the
-- per-unit figure from it. Lines with no discount, or a zero/NULL quantity,
-- simply get 0 — never a division by zero.
UPDATE sale_items
   SET unit_discount = CASE
        WHEN COALESCE(discount, 0) > 0 AND COALESCE(quantity, 0) > 0
            THEN discount / quantity
        ELSE 0
   END;

COMMIT;

-- ============================================================================
--  Verification
-- ============================================================================
-- Should print 1:
-- SELECT COUNT(*) FROM pragma_table_info('sale_items') WHERE name = 'unit_discount';
--
-- Should print 0 (every line agrees: unit_discount x quantity = discount):
-- SELECT COUNT(*) FROM sale_items
--  WHERE ABS(COALESCE(unit_discount,0) * COALESCE(quantity,0) - COALESCE(discount,0)) > 0.01;
--
-- Spot-check a few discounted lines:
-- SELECT id, quantity, discount, unit_discount FROM sale_items
--  WHERE COALESCE(discount,0) > 0 LIMIT 10;
