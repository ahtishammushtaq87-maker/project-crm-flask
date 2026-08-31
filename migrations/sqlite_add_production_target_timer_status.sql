-- ============================================================================
--  Schema changes for the live (VPS) SQLite database
--
--  Target Tracker: adds a deadline time-of-day (so a live countdown has an
--  exact moment to count down to), a status flag ('active'/'completed'),
--  and a frozen snapshot of the tracker's result math, written once by a
--  background job (or the index page as a fallback) the moment a target's
--  deadline passes. Completed targets move from the Active tab to the new
--  Previous Targets tab using these frozen values instead of recomputing.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_add_production_target_timer_status.sql
--
--  Safe to run on a database that already has some of these: SQLite will
--  report "duplicate column name: ..." for an ALTER that was already applied.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE production_targets ADD COLUMN start_time TIME;
ALTER TABLE production_targets ADD COLUMN end_time TIME;
ALTER TABLE production_targets ADD COLUMN status VARCHAR(20) DEFAULT 'active';
ALTER TABLE production_targets ADD COLUMN result_generated_at DATETIME;
ALTER TABLE production_targets ADD COLUMN final_target_units FLOAT;
ALTER TABLE production_targets ADD COLUMN final_produced_qty FLOAT;
ALTER TABLE production_targets ADD COLUMN final_net_produced FLOAT;
ALTER TABLE production_targets ADD COLUMN final_completion_pct FLOAT;
ALTER TABLE production_targets ADD COLUMN final_result_status VARCHAR(20);
ALTER TABLE production_targets ADD COLUMN final_actual_revenue FLOAT;
ALTER TABLE production_targets ADD COLUMN final_actual_cost FLOAT;
ALTER TABLE production_targets ADD COLUMN final_actual_profit FLOAT;

UPDATE production_targets SET status = 'active' WHERE status IS NULL;

COMMIT;

-- ============================================================================
--  Verification — every row below should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('production_targets') WHERE name = 'end_time';
-- SELECT COUNT(*) FROM pragma_table_info('production_targets') WHERE name = 'status';
-- SELECT COUNT(*) FROM pragma_table_info('production_targets') WHERE name = 'final_net_produced';
-- SELECT COUNT(*) FROM pragma_table_info('production_targets') WHERE name = 'final_produced_qty';
-- SELECT COUNT(*) FROM pragma_table_info('production_targets') WHERE name = 'final_target_units';
