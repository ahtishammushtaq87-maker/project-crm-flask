-- ============================================================================
--  Spreadsheet module (Google Sheets-style workbooks inside the CRM).
--  Six NEW tables, all prefixed "spreadsheet". No existing table or row is
--  changed; users are only referenced by foreign key.
--
--  The app also creates these tables automatically on startup if they are
--  missing (app/sheets/__init__.py -> init_app, CREATE ... IF NOT EXISTS
--  semantics), so running this file by hand is optional.
--
--  Run it on a COPY first, and take a backup before touching production:
--      cp database.db database.db.bak-$(date +%F)
--      sqlite3 database.db < sqlite_spreadsheet_module.sql
--
--  Safe to re-run (IF NOT EXISTS).
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS spreadsheets (
    id                  INTEGER      NOT NULL PRIMARY KEY,
    name                VARCHAR(200) NOT NULL,
    description         TEXT,
    owner_id            INTEGER      NOT NULL REFERENCES users (id),
    created_by          INTEGER      REFERENCES users (id),
    updated_by          INTEGER      REFERENCES users (id),
    created_at          DATETIME     NOT NULL,
    updated_at          DATETIME     NOT NULL,
    version             INTEGER      NOT NULL DEFAULT 1,
    structure_version   INTEGER      NOT NULL DEFAULT 1,
    viewers_can_export  BOOLEAN      NOT NULL DEFAULT 1,
    is_deleted          BOOLEAN      NOT NULL DEFAULT 0,
    deleted_at          DATETIME,
    deleted_by          INTEGER      REFERENCES users (id)
);
CREATE INDEX IF NOT EXISTS ix_spreadsheets_owner_id   ON spreadsheets (owner_id);
CREATE INDEX IF NOT EXISTS ix_spreadsheets_updated_at ON spreadsheets (updated_at);
CREATE INDEX IF NOT EXISTS ix_spreadsheets_is_deleted ON spreadsheets (is_deleted);

CREATE TABLE IF NOT EXISTS spreadsheet_sheets (
    id              INTEGER      NOT NULL PRIMARY KEY,
    spreadsheet_id  INTEGER      NOT NULL REFERENCES spreadsheets (id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    position        INTEGER      NOT NULL DEFAULT 0,
    color           VARCHAR(20),
    is_hidden       BOOLEAN      NOT NULL DEFAULT 0,
    row_count       INTEGER      NOT NULL DEFAULT 1000,
    col_count       INTEGER      NOT NULL DEFAULT 26,
    frozen_rows     INTEGER      NOT NULL DEFAULT 0,
    frozen_cols     INTEGER      NOT NULL DEFAULT 0,
    props           TEXT,        -- JSON: column widths, row heights, merges, filter, validation, conditional formats
    props_version   INTEGER      NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL,
    updated_at      DATETIME     NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_spreadsheet_sheets_spreadsheet_id ON spreadsheet_sheets (spreadsheet_id);

CREATE TABLE IF NOT EXISTS spreadsheet_cells (
    id              INTEGER  NOT NULL PRIMARY KEY,
    spreadsheet_id  INTEGER  NOT NULL REFERENCES spreadsheets (id) ON DELETE CASCADE,
    sheet_id        INTEGER  NOT NULL REFERENCES spreadsheet_sheets (id) ON DELETE CASCADE,
    "row"           INTEGER  NOT NULL,   -- 0-based
    col             INTEGER  NOT NULL,   -- 0-based
    value           TEXT,                -- raw input; formulas start with '='
    fmt             TEXT,                -- JSON cell style
    version         INTEGER  NOT NULL DEFAULT 1,
    updated_by      INTEGER  REFERENCES users (id),
    updated_at      DATETIME,
    CONSTRAINT uq_spreadsheet_cell_pos UNIQUE (sheet_id, "row", col)
);
CREATE INDEX IF NOT EXISTS ix_spreadsheet_cells_book_version ON spreadsheet_cells (spreadsheet_id, version);

CREATE TABLE IF NOT EXISTS spreadsheet_permissions (
    id              INTEGER     NOT NULL PRIMARY KEY,
    spreadsheet_id  INTEGER     NOT NULL REFERENCES spreadsheets (id) ON DELETE CASCADE,
    user_id         INTEGER     NOT NULL REFERENCES users (id),
    sheet_id        INTEGER     REFERENCES spreadsheet_sheets (id) ON DELETE CASCADE,  -- NULL = whole spreadsheet (reserved for per-sheet access)
    role            VARCHAR(20) NOT NULL DEFAULT 'viewer',                              -- viewer | editor | manager
    granted_by      INTEGER     REFERENCES users (id),
    created_at      DATETIME    NOT NULL,
    updated_at      DATETIME    NOT NULL,
    CONSTRAINT uq_spreadsheet_permission UNIQUE (spreadsheet_id, user_id, sheet_id)
);
CREATE INDEX IF NOT EXISTS ix_spreadsheet_permissions_spreadsheet_id ON spreadsheet_permissions (spreadsheet_id);
CREATE INDEX IF NOT EXISTS ix_spreadsheet_permissions_user_id        ON spreadsheet_permissions (user_id);

CREATE TABLE IF NOT EXISTS spreadsheet_user_state (
    id              INTEGER  NOT NULL PRIMARY KEY,
    spreadsheet_id  INTEGER  NOT NULL REFERENCES spreadsheets (id) ON DELETE CASCADE,
    user_id         INTEGER  NOT NULL REFERENCES users (id),
    is_favorite     BOOLEAN  NOT NULL DEFAULT 0,
    last_opened_at  DATETIME,
    CONSTRAINT uq_spreadsheet_user_state UNIQUE (spreadsheet_id, user_id)
);
CREATE INDEX IF NOT EXISTS ix_spreadsheet_user_state_spreadsheet_id ON spreadsheet_user_state (spreadsheet_id);
CREATE INDEX IF NOT EXISTS ix_spreadsheet_user_state_user_id        ON spreadsheet_user_state (user_id);

CREATE TABLE IF NOT EXISTS spreadsheet_activity (
    id              INTEGER      NOT NULL PRIMARY KEY,
    spreadsheet_id  INTEGER      NOT NULL REFERENCES spreadsheets (id) ON DELETE CASCADE,
    user_id         INTEGER      REFERENCES users (id),
    version         INTEGER,
    action          VARCHAR(40)  NOT NULL,
    summary         VARCHAR(500),
    change_count    INTEGER      DEFAULT 0,
    created_at      DATETIME     NOT NULL,
    updated_at      DATETIME     NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_spreadsheet_activity_spreadsheet_id ON spreadsheet_activity (spreadsheet_id);
CREATE INDEX IF NOT EXISTS ix_spreadsheet_activity_created_at     ON spreadsheet_activity (created_at);

COMMIT;

-- ============================================================================
--  Verification - should print 6
-- ============================================================================
-- SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name LIKE 'spreadsheet%';

-- ============================================================================
--  PostgreSQL equivalent: same statements with
--      INTEGER NOT NULL PRIMARY KEY  ->  SERIAL PRIMARY KEY
--      DATETIME                      ->  TIMESTAMP
--      BOOLEAN DEFAULT 1 / 0         ->  BOOLEAN DEFAULT TRUE / FALSE
--  (wrap the statements in BEGIN; ... COMMIT; and drop the PRAGMA line)
-- ============================================================================
