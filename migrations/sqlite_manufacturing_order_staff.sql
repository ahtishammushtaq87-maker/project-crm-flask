-- ============================================================================
--  New table: manufacturing_order_staff
--
--  Lets a Manufacturing Order have one or more Staff (from HR) assigned to
--  it. When staff are assigned, the order's labor cost is auto-computed
--  from their salaries (daily_salary, falling back to monthly_salary / 30)
--  times the number of days in the order's start/end date range, instead
--  of the older BOM.labor_cost x quantity estimate. Orders with nobody
--  assigned keep using that original calculation - nothing existing
--  changes behavior.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_manufacturing_order_staff.sql
--
--  Safe to run again later: CREATE TABLE IF NOT EXISTS is a no-op if the
--  table already exists (e.g. the app's own startup auto-migrator already
--  created it for you).
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS manufacturing_order_staff (
    id          INTEGER NOT NULL,
    mo_id       INTEGER NOT NULL,
    staff_id    INTEGER NOT NULL,
    daily_rate  FLOAT DEFAULT 0,
    days        FLOAT DEFAULT 0,
    labor_cost  FLOAT DEFAULT 0,
    created_at  DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(mo_id) REFERENCES manufacturing_orders (id),
    FOREIGN KEY(staff_id) REFERENCES staff (id),
    UNIQUE (mo_id, staff_id)
);

CREATE INDEX IF NOT EXISTS ix_manufacturing_order_staff_mo_id    ON manufacturing_order_staff (mo_id);
CREATE INDEX IF NOT EXISTS ix_manufacturing_order_staff_staff_id ON manufacturing_order_staff (staff_id);

COMMIT;

-- ============================================================================
--  Verification — should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name = 'manufacturing_order_staff';
