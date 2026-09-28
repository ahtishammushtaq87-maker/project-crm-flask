-- ============================================================================
--  Per-order staff exclusions for a Manufacturing Order's "Staff / Salary
--  Allocation" card: a row here means that staff member's salary is NOT
--  charged to that order's labor cost. No rows = every staff member
--  included (the existing behaviour), so nothing changes until you untick.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_manufacturing_order_staff_exclusions.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS manufacturing_order_staff_exclusions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mo_id       INTEGER NOT NULL REFERENCES manufacturing_orders(id) ON DELETE CASCADE,
    staff_id    INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    created_by  INTEGER REFERENCES users(id),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_mo_staff_exclusion_once UNIQUE (mo_id, staff_id)
);

CREATE INDEX IF NOT EXISTS ix_mo_staff_exclusions_mo_id ON manufacturing_order_staff_exclusions (mo_id);
CREATE INDEX IF NOT EXISTS ix_mo_staff_exclusions_staff_id ON manufacturing_order_staff_exclusions (staff_id);

-- ============================================================================
--  Verification - should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='manufacturing_order_staff_exclusions';
