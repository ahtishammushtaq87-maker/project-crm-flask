-- ============================================================================
--  Perfect-attendance bonus: marks Bonuses & Adjustments rows created
--  automatically by app/services/attendance_bonus.py, which awards one day's
--  pay to any staff member whose month was worked exactly to the required
--  hours with no overtime logged.
--
--  This column is also the job's idempotency key: one auto row per staff per
--  payroll month in ANY status, so rejecting a row permanently suppresses it
--  instead of it being re-created on the next run.
--
--  Existing rows are all manual, so they backfill to 0 - nothing that works
--  today changes behaviour.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_salary_adjustment_auto_attendance_bonus.sql
--
--  Safe to run on a database that already has this column: SQLite will
--  report "duplicate column name: is_auto_attendance_bonus" and skip it.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE salary_adjustments ADD COLUMN is_auto_attendance_bonus BOOLEAN DEFAULT 0;

UPDATE salary_adjustments SET is_auto_attendance_bonus = 0 WHERE is_auto_attendance_bonus IS NULL;

CREATE INDEX IF NOT EXISTS ix_salary_adjustments_is_auto_attendance_bonus
    ON salary_adjustments (is_auto_attendance_bonus);

COMMIT;

-- ============================================================================
--  Verification — should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('salary_adjustments')
--   WHERE name = 'is_auto_attendance_bonus';
