-- ============================================================================
--  Item Structure files: any number of files of ANY type (PDF drawings,
--  spec sheets, photos, spreadsheets, ...) attached to a product.
--  Uploaded from Inventory > Add/Edit Product ("Item Structure" section)
--  and viewed from Products list > Actions > Item Structure.
--
--  Files are stored on disk under app/uploads/product_structure/<product_id>/
--  (outside app/static - only served to logged-in users).
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_product_structure_files.sql
--
--  Safe to re-run (IF NOT EXISTS).
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS product_structure_files (
    id            INTEGER      NOT NULL PRIMARY KEY,
    product_id    INTEGER      NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    original_name VARCHAR(255) NOT NULL,
    stored_path   VARCHAR(500) NOT NULL,
    mime_type     VARCHAR(150),
    file_size     INTEGER      DEFAULT 0,
    uploaded_by   INTEGER      REFERENCES users (id),
    created_at    DATETIME
);

CREATE INDEX IF NOT EXISTS ix_product_structure_files_product_id
    ON product_structure_files (product_id);

COMMIT;

-- ============================================================================
--  Verification - should print 1
-- ============================================================================
-- SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'product_structure_files';

-- ============================================================================
--  PostgreSQL equivalent
-- ============================================================================
-- CREATE TABLE IF NOT EXISTS product_structure_files (
--     id            SERIAL       PRIMARY KEY,
--     product_id    INTEGER      NOT NULL REFERENCES products (id) ON DELETE CASCADE,
--     original_name VARCHAR(255) NOT NULL,
--     stored_path   VARCHAR(500) NOT NULL,
--     mime_type     VARCHAR(150),
--     file_size     INTEGER      DEFAULT 0,
--     uploaded_by   INTEGER      REFERENCES users (id),
--     created_at    TIMESTAMP
-- );
-- CREATE INDEX IF NOT EXISTS ix_product_structure_files_product_id
--     ON product_structure_files (product_id);
