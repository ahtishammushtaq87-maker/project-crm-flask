-- ============================================================================
--  Schema changes for the live (VPS) SQLite database
--
--  1. staff.left_date            - date a staff member was marked as having
--                                   left the company (Staff.is_active is
--                                   flipped to 0 at the same time; that flag
--                                   already drives every attendance/payroll/
--                                   custodian-dropdown exclusion in the app)
--  2. staff_reviews (new table)  - permanent star-rating + note log per staff
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_add_staff_left_date_and_reviews.sql
--
--  Safe to run on a database that already has some of these: SQLite will
--  report "duplicate column name: ..." for an ALTER that was already applied
--  and skip it. That message is expected — the CREATE statement uses
--  IF NOT EXISTS and is always safe.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE staff ADD COLUMN left_date DATE;

CREATE TABLE IF NOT EXISTS staff_reviews (
    id          INTEGER NOT NULL,
    staff_id    INTEGER NOT NULL,
    rating      INTEGER NOT NULL,
    comment     TEXT,
    created_by  INTEGER,
    created_at  DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(staff_id) REFERENCES staff (id),
    FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_staff_reviews_staff_id ON staff_reviews (staff_id);

COMMIT;

-- ============================================================================
--  Verification — every row below should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('staff') WHERE name = 'left_date';
-- SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name = 'staff_reviews';
