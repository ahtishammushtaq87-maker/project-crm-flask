-- ============================================================================
--  Optional receipt / proof image on a Salary Advance.
--
--    salary_advances.image_path
--        project-root-relative path ("app/static/uploads/advances/...") of the
--        image uploaded, captured or pasted on Record Advance. NULL = none.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_salary_advance_image.sql
--
--  Safe to run on a database that already has this column: SQLite will
--  report "duplicate column name" and skip it.
-- ============================================================================

BEGIN TRANSACTION;

ALTER TABLE salary_advances ADD COLUMN image_path VARCHAR(255);

COMMIT;
