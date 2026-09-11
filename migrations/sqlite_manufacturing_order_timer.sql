-- ============================================================================
--  Manufacturing Order auto-stop timer: adds an optional time-of-day to the
--  existing Start/End Date fields, plus a timer_stopped flag that a
--  background job (and the Orders list page as a fallback) flips once the
--  End Date + End Time moment passes. This ONLY moves the order from the
--  Active tab to the Previous tab on the Manufacturing Orders list - it
--  never touches status, stock, produced_qty, or any completion/reversal
--  logic (batch complete, undo, delete all keep working identically).
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_manufacturing_order_timer.sql
--
--  Safe to run on a database that already has these columns: SQLite will
--  report "duplicate column name" and skip it.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE manufacturing_orders ADD COLUMN start_time TIME;
ALTER TABLE manufacturing_orders ADD COLUMN end_time TIME;
ALTER TABLE manufacturing_orders ADD COLUMN timer_stopped BOOLEAN DEFAULT 0;
ALTER TABLE manufacturing_orders ADD COLUMN timer_stopped_at DATETIME;

-- Every order that exists right now has never had a timer, so it stays on
-- the Active tab until its own End Date/Time (if any) actually passes.
UPDATE manufacturing_orders SET timer_stopped = 0 WHERE timer_stopped IS NULL;

CREATE INDEX IF NOT EXISTS ix_manufacturing_orders_timer_stopped ON manufacturing_orders (timer_stopped);

COMMIT;

-- ============================================================================
--  Verification — should print 4
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('manufacturing_orders')
--   WHERE name IN ('start_time', 'end_time', 'timer_stopped', 'timer_stopped_at');
