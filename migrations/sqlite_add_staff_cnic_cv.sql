-- ============================================================================
--  Schema changes for the live (VPS) SQLite database
--
--  Adds CNIC and CV document-upload columns to the staff table (Staff
--  Add/Edit form now supports uploading these via camera capture or file
--  picker, same as the existing Agreement Letter field).
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_add_staff_cnic_cv.sql
--
--  Safe to run on a database that already has these: SQLite will report
--  "duplicate column name: ..." for an ALTER that was already applied.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE staff ADD COLUMN cnic VARCHAR(255);
ALTER TABLE staff ADD COLUMN cv VARCHAR(255);

COMMIT;

-- ============================================================================
--  Verification — both rows below should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM pragma_table_info('staff') WHERE name = 'cnic';
-- SELECT COUNT(*) FROM pragma_table_info('staff') WHERE name = 'cv';
