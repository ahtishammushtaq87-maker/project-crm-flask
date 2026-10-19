-- ============================================================================
--  Schema change for the live (VPS) SQLite database — "Keep" checkbox on
--  Database Backups
--
--  Adds:  database_backups.is_protected
--
--  A kept (protected) backup is never deleted by the 10-backup retention and
--  doesn't count toward the 10; only deleting it by hand removes it. Existing
--  backups start unkept (0), so nothing changes until a box is ticked. The
--  flag is also mirrored as a <filename>.keep file in instance/backups/,
--  which is what survives a database restore.
--
--  The app adds this column by itself on startup (auto-migration); run this
--  only if you prefer to apply it by hand. Back up first:
--      cp instance/database.db instance/database.db.bak-$(date +%F)
--      sqlite3 instance/database.db < migrations/sqlite_database_backup_keep.sql
--
--  Re-running stops at "duplicate column name" — harmless.
-- ============================================================================

ALTER TABLE database_backups ADD COLUMN is_protected BOOLEAN NOT NULL DEFAULT 0;

-- Verification (should print 1):
-- SELECT COUNT(*) FROM pragma_table_info('database_backups') WHERE name = 'is_protected';
