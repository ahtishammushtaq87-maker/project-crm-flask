-- =====================================================================
-- LIVE DATABASE MIGRATION  (SQLite)
-- Adds the `needs_approval` review flag used by the new behaviour:
-- "staff payments/advances apply to the invoice immediately, but still
--  raise an approval request to the admin".
--
-- BACK UP FIRST:
--     cp instance/database.db instance/database.db.bak
--
-- IMPORTANT — run PART 1 and PART 2 as SEPARATE commands:
--
--     sqlite3 instance/database.db < migrate_needs_approval.sql        -- (PART 1 + 2 in one go, see note)
--
-- SQLite has no "ADD COLUMN IF NOT EXISTS". If the column already exists
-- the ALTER in PART 1 fails with "duplicate column name: needs_approval"
-- AND ABORTS THE REST OF THE FILE. That error is harmless in itself, but
-- PART 2 must still be run. So:
--
--   * Run PART 0 first to see whether the columns exist.
--   * If they do NOT exist  -> run PART 1, then PART 2.
--   * If they ALREADY exist -> SKIP PART 1 and run PART 2 only.
--
-- This app auto-adds missing columns on startup (app/__init__.py), so on
-- a server that has already booted the new code the columns will usually
-- exist and you only need PART 2.
--
-- Prefer no thinking about it? Run the idempotent Python version instead:
--     python migrate_needs_approval.py
-- =====================================================================


-- =====================================================================
-- PART 0 — do the columns already exist?  (1 = yes, 0 = no)
-- =====================================================================
SELECT 'payments.needs_approval'          AS column_name,
       COUNT(*)                           AS already_exists
FROM   pragma_table_info('payments')
WHERE  name = 'needs_approval';

SELECT 'customer_advances.needs_approval' AS column_name,
       COUNT(*)                           AS already_exists
FROM   pragma_table_info('customer_advances')
WHERE  name = 'needs_approval';


-- =====================================================================
-- PART 1 — add the columns.  RUN ONLY FOR THE TABLES PART 0 REPORTED 0.
-- (A "duplicate column name" error here just means it already exists.)
-- =====================================================================
ALTER TABLE payments          ADD COLUMN needs_approval BOOLEAN DEFAULT 0;
ALTER TABLE customer_advances ADD COLUMN needs_approval BOOLEAN DEFAULT 0;


-- =====================================================================
-- PART 2 — backfill + indexes + verification.
-- ALWAYS RUN THIS. Safe to run repeatedly.
--
-- Every existing row is set to 0 ("not awaiting review") on purpose:
-- rows that are currently pending (is_approved = 0) have NOT had their
-- amount added to sales.paid_amount, so they must keep using the original
-- "approve to apply" path. Marking them 1 would make the admin's Approve
-- button skip adding the money and leave those invoices short-paid.
-- =====================================================================
UPDATE payments          SET needs_approval = 0 WHERE needs_approval IS NULL;
UPDATE customer_advances SET needs_approval = 0 WHERE needs_approval IS NULL;

-- If the column was auto-created by the app it can carry the string
-- 'False' as its default, so normalise anything non-numeric to 0.
UPDATE payments          SET needs_approval = 0 WHERE needs_approval NOT IN (0, 1);
UPDATE customer_advances SET needs_approval = 0 WHERE needs_approval NOT IN (0, 1);

CREATE INDEX IF NOT EXISTS ix_payments_needs_approval
    ON payments (needs_approval);
CREATE INDEX IF NOT EXISTS ix_customer_advances_needs_approval
    ON customer_advances (needs_approval);


-- =====================================================================
-- PART 3 — verify. Both bad_rows counts must be 0.
-- =====================================================================
SELECT 'payments with bad needs_approval'  AS check_name,
       COUNT(*)                            AS bad_rows
FROM   payments
WHERE  needs_approval IS NULL OR needs_approval NOT IN (0, 1);

SELECT 'advances with bad needs_approval'  AS check_name,
       COUNT(*)                            AS bad_rows
FROM   customer_advances
WHERE  needs_approval IS NULL OR needs_approval NOT IN (0, 1);

SELECT 'items awaiting admin attention'    AS check_name,
       COUNT(*)                            AS n
FROM   payments
WHERE  (is_approved = 0 OR needs_approval = 1) AND is_rejected = 0;


-- =====================================================================
-- APPENDIX — PostgreSQL version
-- Use this instead of everything above if the live server runs Postgres
-- (config.py falls back to SQLite only when DATABASE_URL is unset).
-- Postgres DOES support IF NOT EXISTS, so this is a single idempotent
-- block — no PART 1 / PART 2 juggling.
-- =====================================================================
-- ALTER TABLE payments          ADD COLUMN IF NOT EXISTS needs_approval BOOLEAN DEFAULT FALSE;
-- ALTER TABLE customer_advances ADD COLUMN IF NOT EXISTS needs_approval BOOLEAN DEFAULT FALSE;
--
-- UPDATE payments          SET needs_approval = FALSE WHERE needs_approval IS NULL;
-- UPDATE customer_advances SET needs_approval = FALSE WHERE needs_approval IS NULL;
--
-- CREATE INDEX IF NOT EXISTS ix_payments_needs_approval
--     ON payments (needs_approval);
-- CREATE INDEX IF NOT EXISTS ix_customer_advances_needs_approval
--     ON customer_advances (needs_approval);
--
-- -- verify (both must be 0)
-- SELECT COUNT(*) AS bad_rows FROM payments          WHERE needs_approval IS NULL;
-- SELECT COUNT(*) AS bad_rows FROM customer_advances WHERE needs_approval IS NULL;
