"""Database models for the Spreadsheet module.

All tables are new and prefixed ``spreadsheet``; nothing here touches an
existing CRM table (users are only referenced by foreign key).

Storage layout
--------------
* ``spreadsheets``             one row per workbook (name, owner, version).
* ``spreadsheet_sheets``       tabs of a workbook. Layout that isn't per-cell
                               (column widths, merges, filters, validation,
                               conditional formats, hidden rows...) lives in
                               ``props`` as a small JSON document.
* ``spreadsheet_cells``        one row per non-empty cell, so saving touches
                               only the cells that changed and a sheet loads
                               without reading the others.
* ``spreadsheet_permissions``  who may open/edit/share a workbook. ``sheet_id``
                               is reserved for per-sheet access (NULL = the
                               whole workbook, the only level used today).
* ``spreadsheet_user_state``   per-user favourite flag and last-opened time.
* ``spreadsheet_activity``     audit trail / version history.

Concurrency: every saved batch bumps ``Spreadsheet.version``; each cell keeps
the version that last wrote it, which is how a save detects that another user
changed the same cells in the meantime (see services.apply_batch).
"""
from datetime import datetime

from app import db


class Spreadsheet(db.Model):
    __tablename__ = 'spreadsheets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    # Bumped by every saved batch; the client sends the version it last saw.
    version = db.Column(db.Integer, default=1, nullable=False)
    # Version of the last change that moved cells around (insert/delete
    # rows or columns, sort, sheet deleted). Cell coordinates sent by a
    # client older than this can no longer be trusted.
    structure_version = db.Column(db.Integer, default=1, nullable=False)
    viewers_can_export = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime)
    deleted_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    owner = db.relationship('User', foreign_keys=[owner_id])
    updater = db.relationship('User', foreign_keys=[updated_by])
    sheets = db.relationship('SpreadsheetSheet', backref='spreadsheet', lazy='dynamic',
                             cascade='all, delete-orphan', order_by='SpreadsheetSheet.position')
    permissions = db.relationship('SpreadsheetPermission', backref='spreadsheet', lazy='dynamic',
                                  cascade='all, delete-orphan')


class SpreadsheetSheet(db.Model):
    __tablename__ = 'spreadsheet_sheets'

    id = db.Column(db.Integer, primary_key=True)
    spreadsheet_id = db.Column(db.Integer, db.ForeignKey('spreadsheets.id', ondelete='CASCADE'),
                               nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    color = db.Column(db.String(20))
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    row_count = db.Column(db.Integer, default=1000, nullable=False)
    col_count = db.Column(db.Integer, default=26, nullable=False)
    frozen_rows = db.Column(db.Integer, default=0, nullable=False)
    frozen_cols = db.Column(db.Integer, default=0, nullable=False)
    props = db.Column(db.Text)                 # JSON, see validators.clean_props
    props_version = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SpreadsheetCell(db.Model):
    __tablename__ = 'spreadsheet_cells'

    id = db.Column(db.Integer, primary_key=True)
    # Denormalised so "what changed in this workbook since version N" is a
    # single indexed query.
    spreadsheet_id = db.Column(db.Integer, db.ForeignKey('spreadsheets.id', ondelete='CASCADE'),
                               nullable=False)
    sheet_id = db.Column(db.Integer, db.ForeignKey('spreadsheet_sheets.id', ondelete='CASCADE'),
                         nullable=False)
    row = db.Column(db.Integer, nullable=False)    # 0-based
    col = db.Column(db.Integer, nullable=False)    # 0-based
    # What the user typed: plain text, a number as text, or a formula
    # starting with '='. NULL = cleared (kept so other users see the clear).
    value = db.Column(db.Text)
    fmt = db.Column(db.Text)                       # JSON style, see validators.clean_fmt
    version = db.Column(db.Integer, default=1, nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('sheet_id', 'row', 'col', name='uq_spreadsheet_cell_pos'),
        db.Index('ix_spreadsheet_cells_book_version', 'spreadsheet_id', 'version'),
    )


class SpreadsheetPermission(db.Model):
    __tablename__ = 'spreadsheet_permissions'

    ROLES = ('viewer', 'editor', 'manager')

    id = db.Column(db.Integer, primary_key=True)
    spreadsheet_id = db.Column(db.Integer, db.ForeignKey('spreadsheets.id', ondelete='CASCADE'),
                               nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    # Reserved for per-sheet access; NULL = the whole spreadsheet.
    sheet_id = db.Column(db.Integer, db.ForeignKey('spreadsheet_sheets.id', ondelete='CASCADE'))
    role = db.Column(db.String(20), nullable=False, default='viewer')
    granted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint('spreadsheet_id', 'user_id', 'sheet_id', name='uq_spreadsheet_permission'),
    )


class SpreadsheetUserState(db.Model):
    __tablename__ = 'spreadsheet_user_state'

    id = db.Column(db.Integer, primary_key=True)
    spreadsheet_id = db.Column(db.Integer, db.ForeignKey('spreadsheets.id', ondelete='CASCADE'),
                               nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)
    last_opened_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('spreadsheet_id', 'user_id', name='uq_spreadsheet_user_state'),
    )


class SpreadsheetActivity(db.Model):
    __tablename__ = 'spreadsheet_activity'

    id = db.Column(db.Integer, primary_key=True)
    spreadsheet_id = db.Column(db.Integer, db.ForeignKey('spreadsheets.id', ondelete='CASCADE'),
                               nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    version = db.Column(db.Integer)
    action = db.Column(db.String(40), nullable=False)
    summary = db.Column(db.String(500))
    # Running count for coalesced edit entries ("Edited 42 cells").
    change_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', foreign_keys=[user_id])


ALL_MODELS = (Spreadsheet, SpreadsheetSheet, SpreadsheetCell, SpreadsheetPermission,
              SpreadsheetUserState, SpreadsheetActivity)
