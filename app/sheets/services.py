"""Spreadsheet operations used by the pages and the JSON API.

The functions here never check permissions themselves - callers (api.py,
routes.py) do that first via app.sheets.permissions. Nothing commits except
where noted, so a failed request rolls back cleanly.
"""
from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import func, or_, and_

from app import db
from app.models import User
from app.sheets import validators as V
from app.sheets.models import (Spreadsheet, SpreadsheetSheet, SpreadsheetCell, SpreadsheetPermission,
                               SpreadsheetUserState, SpreadsheetActivity)
from app.sheets.permissions import is_crm_admin, role_for, ROLE_LABELS
from app.sheets.starter_templates import build_template, STATUS_VALIDATION

DEFAULT_ROWS = 1000
DEFAULT_COLS = 26
EDIT_COALESCE = timedelta(minutes=10)


class Conflict(Exception):
    """The client's view of the spreadsheet is out of date."""

    def __init__(self, message: str, by: Optional[str] = None, structural: bool = False):
        super().__init__(message)
        self.by = by
        self.structural = structural


# ── Serialisation ─────────────────────────────────────────────────────────

def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ') if dt else None


def user_label(user: Optional[User]) -> str:
    if not user:
        return 'Unknown'
    return user.username


def sheet_meta(sheet: SpreadsheetSheet) -> dict:
    return {
        'id': sheet.id, 'name': sheet.name, 'position': sheet.position, 'color': sheet.color,
        'hidden': bool(sheet.is_hidden), 'rows': sheet.row_count, 'cols': sheet.col_count,
        'frozen_rows': sheet.frozen_rows, 'frozen_cols': sheet.frozen_cols,
        'props_version': sheet.props_version,
    }


def cell_json(cell: SpreadsheetCell) -> dict:
    return {'r': cell.row, 'c': cell.col, 'v': cell.value, 'f': V.load(cell.fmt)}


def sheet_full(sheet: SpreadsheetSheet) -> dict:
    data = sheet_meta(sheet)
    data['props'] = V.load(sheet.props, {}) or {}
    cells = (SpreadsheetCell.query
             .filter(SpreadsheetCell.sheet_id == sheet.id,
                     or_(SpreadsheetCell.value.isnot(None), SpreadsheetCell.fmt.isnot(None)))
             .all())
    data['cells'] = [cell_json(c) for c in cells]
    return data


def summary(ss: Spreadsheet, user, state: Optional[SpreadsheetUserState] = None,
            share_count: Optional[int] = None, role: Optional[str] = None) -> dict:
    role = role or role_for(user, ss)
    return {
        'id': ss.id,
        'name': ss.name,
        'description': ss.description or '',
        'owner_id': ss.owner_id,
        'owner': user_label(ss.owner),
        'created_at': iso(ss.created_at),
        'updated_at': iso(ss.updated_at),
        'updated_by': user_label(ss.updater) if ss.updated_by else user_label(ss.owner),
        'role': role,
        'role_label': ROLE_LABELS.get(role, ''),
        'shared_count': share_count if share_count is not None else ss.permissions.count(),
        'favorite': bool(state and state.is_favorite),
        'last_opened_at': iso(state.last_opened_at) if state else None,
        'deleted': bool(ss.is_deleted),
    }


# ── Listing / search ──────────────────────────────────────────────────────

SORTS = {
    'modified': Spreadsheet.updated_at.desc(),
    'created': Spreadsheet.created_at.desc(),
    'name': func.lower(Spreadsheet.name).asc(),
}


def list_for_user(user, q: str = '', sort: str = 'modified', scope: str = 'all') -> list:
    """Spreadsheets the user may open. Search covers name, description and
    owner. scope: all | mine | shared | favorites | admin_all | deleted
    (the last two for CRM admins only)."""
    admin = is_crm_admin(user)
    query = Spreadsheet.query.join(User, User.id == Spreadsheet.owner_id)

    if scope == 'deleted' and admin:
        query = query.filter(Spreadsheet.is_deleted.is_(True))
    else:
        query = query.filter(Spreadsheet.is_deleted.is_(False))
        shared_ids = db.session.query(SpreadsheetPermission.spreadsheet_id).filter(
            SpreadsheetPermission.user_id == user.id, SpreadsheetPermission.sheet_id.is_(None))
        if scope == 'mine':
            query = query.filter(Spreadsheet.owner_id == user.id)
        elif scope == 'shared':
            query = query.filter(Spreadsheet.id.in_(shared_ids), Spreadsheet.owner_id != user.id)
        elif scope == 'admin_all' and admin:
            pass
        else:
            query = query.filter(or_(Spreadsheet.owner_id == user.id, Spreadsheet.id.in_(shared_ids)))

    q = (q or '').strip()
    if q:
        like = f'%{q.lower()}%'
        query = query.filter(or_(func.lower(Spreadsheet.name).like(like),
                                 func.lower(func.coalesce(Spreadsheet.description, '')).like(like),
                                 func.lower(User.username).like(like)))

    states = {s.spreadsheet_id: s for s in SpreadsheetUserState.query.filter_by(user_id=user.id)}
    if scope == 'favorites':
        fav_ids = [sid for sid, s in states.items() if s.is_favorite]
        query = query.filter(Spreadsheet.id.in_(fav_ids or [-1]))

    if sort == 'owner':
        query = query.order_by(func.lower(User.username).asc(), Spreadsheet.updated_at.desc())
    else:
        query = query.order_by(SORTS.get(sort, SORTS['modified']))

    books = query.limit(1000).all()
    ids = [b.id for b in books]
    counts = dict(db.session.query(SpreadsheetPermission.spreadsheet_id, func.count(SpreadsheetPermission.id))
                  .filter(SpreadsheetPermission.spreadsheet_id.in_(ids or [-1]))
                  .group_by(SpreadsheetPermission.spreadsheet_id).all())
    my_roles = dict(db.session.query(SpreadsheetPermission.spreadsheet_id, SpreadsheetPermission.role)
                    .filter(SpreadsheetPermission.spreadsheet_id.in_(ids or [-1]),
                            SpreadsheetPermission.user_id == user.id,
                            SpreadsheetPermission.sheet_id.is_(None)).all())
    out = []
    for b in books:
        if admin:
            role = 'admin'
        elif b.owner_id == user.id:
            role = 'owner'
        else:
            role = my_roles.get(b.id)
        out.append(summary(b, user, states.get(b.id), counts.get(b.id, 0), role))
    return out


# ── Create / duplicate / delete ───────────────────────────────────────────

def _new_sheet(ss: Spreadsheet, name: str, position: int, rows: int = DEFAULT_ROWS,
               cols: int = DEFAULT_COLS) -> SpreadsheetSheet:
    sheet = SpreadsheetSheet(spreadsheet=ss, name=name, position=position, row_count=rows,
                             col_count=cols, props=V.dump(V.clean_props({})), props_version=ss.version or 1)
    db.session.add(sheet)
    return sheet


def _write_cells(ss: Spreadsheet, sheet: SpreadsheetSheet, cells: Iterable, user_id: Optional[int]):
    now = datetime.utcnow()
    for r, c, value, fmt in cells:
        db.session.add(SpreadsheetCell(
            spreadsheet_id=ss.id, sheet_id=sheet.id, row=r, col=c,
            value=V.clean_value(value), fmt=V.dump(V.clean_fmt(fmt)),
            version=ss.version, updated_by=user_id, updated_at=now))


def create_spreadsheet(user, name: str, description: str = '', template: str = 'blank') -> Spreadsheet:
    name = V.clean_name(name)
    ss = Spreadsheet(name=name, description=(description or '').strip()[:2000] or None,
                     owner_id=user.id, created_by=user.id, updated_by=user.id, version=1, structure_version=1)
    db.session.add(ss)
    db.session.flush()

    tmpl = build_template(template)
    if tmpl:
        sheet = _new_sheet(ss, tmpl['name'], 0)
        sheet.frozen_rows = tmpl.get('frozen_rows', 0)
        props = dict(tmpl.get('props') or {})
        if template in STATUS_VALIDATION:
            col, values = STATUS_VALIDATION[template]
            props['dv'] = [{'r1': 1, 'c1': col, 'r2': 200, 'c2': col, 'type': 'list',
                            'values': values, 'strict': True}]
        sheet.props = V.dump(V.clean_props(props))
        db.session.flush()
        _write_cells(ss, sheet, tmpl['cells'], user.id)
    else:
        _new_sheet(ss, 'Sheet1', 0)
    db.session.flush()
    record_activity(ss, user, 'created', f'Created spreadsheet "{name}"')
    return ss


def copy_sheet_cells(ss: Spreadsheet, src: SpreadsheetSheet, dst: SpreadsheetSheet, user_id):
    rows = (SpreadsheetCell.query
            .filter(SpreadsheetCell.sheet_id == src.id,
                    or_(SpreadsheetCell.value.isnot(None), SpreadsheetCell.fmt.isnot(None))).all())
    now = datetime.utcnow()
    for c in rows:
        db.session.add(SpreadsheetCell(spreadsheet_id=ss.id, sheet_id=dst.id, row=c.row, col=c.col,
                                       value=c.value, fmt=c.fmt, version=ss.version,
                                       updated_by=user_id, updated_at=now))


def duplicate_spreadsheet(user, src: Spreadsheet, name: Optional[str] = None) -> Spreadsheet:
    name = V.clean_name(name or f'Copy of {src.name}'[:V.MAX_NAME])
    ss = Spreadsheet(name=name, description=src.description, owner_id=user.id, created_by=user.id,
                     updated_by=user.id, version=1, structure_version=1,
                     viewers_can_export=src.viewers_can_export)
    db.session.add(ss)
    db.session.flush()
    for s in src.sheets.all():
        copy = SpreadsheetSheet(spreadsheet=ss, name=s.name, position=s.position, color=s.color,
                                is_hidden=s.is_hidden, row_count=s.row_count, col_count=s.col_count,
                                frozen_rows=s.frozen_rows, frozen_cols=s.frozen_cols, props=s.props,
                                props_version=1)
        db.session.add(copy)
        db.session.flush()
        copy_sheet_cells(ss, s, copy, user.id)
    record_activity(ss, user, 'created', f'Duplicated from "{src.name}"')
    return ss


def _add_parsed_sheet(ss: Spreadsheet, user, parsed: dict, position: int) -> SpreadsheetSheet:
    """One sheet from io.parse_upload output."""
    cells = parsed.get('cells') or []
    max_r = max((c[0] for c in cells), default=-1)
    max_c = max((c[1] for c in cells), default=-1)
    name = _unique_sheet_name(ss, V.clean_name(parsed.get('name') or 'Imported', V.MAX_SHEET_NAME, 'Sheet name'))
    sheet = _new_sheet(ss, name, position, max(DEFAULT_ROWS, max_r + 1 + 100), max(DEFAULT_COLS, max_c + 1))
    sheet.props = V.dump(V.clean_props(parsed.get('props') or {}))
    sheet.frozen_rows = V._int(parsed.get('frozen_rows'), 0, 50) or 0
    sheet.frozen_cols = V._int(parsed.get('frozen_cols'), 0, 26) or 0
    sheet.color = V.color(parsed.get('color'))
    sheet.is_hidden = bool(parsed.get('hidden'))
    db.session.flush()
    _write_cells(ss, sheet, ((r, c, v, f) for r, c, v, f in cells
                             if r < V.MAX_ROWS and c < V.MAX_COLS), user.id)
    return sheet


def _ensure_visible_sheet(ss: Spreadsheet):
    sheets = ss.sheets.all()
    if sheets and all(s.is_hidden for s in sheets):
        sheets[0].is_hidden = False


def create_from_import(user, name: str, parsed_sheets: list) -> Spreadsheet:
    name = V.clean_name((name or 'Imported spreadsheet')[:V.MAX_NAME])
    ss = Spreadsheet(name=name, owner_id=user.id, created_by=user.id, updated_by=user.id,
                     version=1, structure_version=1)
    db.session.add(ss)
    db.session.flush()
    for i, parsed in enumerate(parsed_sheets):
        _add_parsed_sheet(ss, user, parsed, i)
    _ensure_visible_sheet(ss)
    record_activity(ss, user, 'created', f'Imported spreadsheet "{name}"')
    return ss


def add_imported_sheets(ss: Spreadsheet, user, parsed_sheets: list) -> list:
    """Add imported data as NEW sheets - existing sheets are never touched."""
    if ss.sheets.count() + len(parsed_sheets) > 200:
        raise V.ValidationError('A spreadsheet can have at most 200 sheets.')
    ss.version = (ss.version or 1) + 1
    start = (db.session.query(func.max(SpreadsheetSheet.position)).filter_by(spreadsheet_id=ss.id).scalar() or 0) + 1
    added = [_add_parsed_sheet(ss, user, parsed, start + i) for i, parsed in enumerate(parsed_sheets)]
    for s in added:
        s.props_version = ss.version
    ss.updated_at, ss.updated_by = datetime.utcnow(), user.id
    record_activity(ss, user, 'structure', f'Imported {len(added)} sheet(s)')
    return added


def soft_delete(ss: Spreadsheet, user):
    ss.is_deleted = True
    ss.deleted_at = datetime.utcnow()
    ss.deleted_by = user.id
    record_activity(ss, user, 'deleted', 'Deleted spreadsheet')


def restore(ss: Spreadsheet, user):
    ss.is_deleted = False
    ss.deleted_at = None
    ss.deleted_by = None
    record_activity(ss, user, 'restored', 'Restored spreadsheet')


# ── Per-user state ────────────────────────────────────────────────────────

def user_state(ss: Spreadsheet, user) -> SpreadsheetUserState:
    state = SpreadsheetUserState.query.filter_by(spreadsheet_id=ss.id, user_id=user.id).first()
    if not state:
        state = SpreadsheetUserState(spreadsheet_id=ss.id, user_id=user.id)
        db.session.add(state)
    return state


def mark_opened(ss: Spreadsheet, user):
    user_state(ss, user).last_opened_at = datetime.utcnow()


# ── Activity / version history ────────────────────────────────────────────

def record_activity(ss: Spreadsheet, user, action: str, summary_text: str, count: int = 0,
                    coalesce: bool = False):
    """Append to the spreadsheet's history. Consecutive edits by the same
    user within EDIT_COALESCE fold into one entry instead of one per save."""
    now = datetime.utcnow()
    uid = getattr(user, 'id', None)
    if coalesce:
        last = (SpreadsheetActivity.query.filter_by(spreadsheet_id=ss.id)
                .order_by(SpreadsheetActivity.id.desc()).first())
        if (last and last.user_id == uid and last.action == action
                and now - last.updated_at <= EDIT_COALESCE):
            last.change_count = (last.change_count or 0) + count
            last.version = ss.version
            last.updated_at = now
            last.summary = summary_text.format(n=last.change_count)[:500]
            return last
    entry = SpreadsheetActivity(spreadsheet_id=ss.id, user_id=uid, version=ss.version, action=action,
                                change_count=count, summary=summary_text.format(n=count)[:500],
                                created_at=now, updated_at=now)
    db.session.add(entry)
    return entry


def history(ss: Spreadsheet, limit: int = 200) -> list:
    rows = (SpreadsheetActivity.query.filter_by(spreadsheet_id=ss.id)
            .order_by(SpreadsheetActivity.updated_at.desc()).limit(limit).all())
    return [{'id': a.id, 'user': user_label(a.user), 'action': a.action, 'summary': a.summary,
             'version': a.version, 'at': iso(a.updated_at), 'started_at': iso(a.created_at)} for a in rows]


# ── Sharing ───────────────────────────────────────────────────────────────

def permissions_list(ss: Spreadsheet) -> list:
    rows = (SpreadsheetPermission.query.filter_by(spreadsheet_id=ss.id, sheet_id=None)
            .join(User, User.id == SpreadsheetPermission.user_id)
            .order_by(func.lower(User.username)).all())
    out = [{'user_id': ss.owner_id, 'username': user_label(ss.owner),
            'email': getattr(ss.owner, 'email', ''), 'crm_role': getattr(ss.owner, 'role', ''),
            'role': 'owner', 'role_label': 'Owner'}]
    for p in rows:
        out.append({'user_id': p.user_id, 'username': user_label(p.user), 'email': p.user.email,
                    'crm_role': p.user.role, 'role': p.role, 'role_label': ROLE_LABELS[p.role],
                    'active': bool(p.user.is_active)})
    return out


def search_users(q: str, limit: int = 20) -> list:
    query = User.query.filter(User.is_active.is_(True))
    q = (q or '').strip().lower()
    if q:
        like = f'%{q}%'
        query = query.filter(or_(func.lower(User.username).like(like), func.lower(User.email).like(like)))
    return [{'user_id': u.id, 'username': u.username, 'email': u.email, 'crm_role': u.role}
            for u in query.order_by(func.lower(User.username)).limit(limit).all()]


def set_permission(ss: Spreadsheet, actor, target: User, role: str) -> SpreadsheetPermission:
    perm = SpreadsheetPermission.query.filter_by(spreadsheet_id=ss.id, user_id=target.id, sheet_id=None).first()
    now = datetime.utcnow()
    if perm:
        old = perm.role
        perm.role, perm.updated_at, perm.granted_by = role, now, actor.id
        record_activity(ss, actor, 'permission', f'Changed {target.username} from {ROLE_LABELS[old]} to {ROLE_LABELS[role]}')
    else:
        perm = SpreadsheetPermission(spreadsheet_id=ss.id, user_id=target.id, role=role, granted_by=actor.id,
                                     created_at=now, updated_at=now)
        db.session.add(perm)
        record_activity(ss, actor, 'shared', f'Shared with {target.username} as {ROLE_LABELS[role]}')
    return perm


def transfer_ownership(ss: Spreadsheet, actor, new_owner: User):
    old_owner = ss.owner
    SpreadsheetPermission.query.filter_by(spreadsheet_id=ss.id, user_id=new_owner.id, sheet_id=None).delete()
    ss.owner_id = new_owner.id
    # The previous owner keeps working on it as a manager.
    if old_owner and old_owner.id != new_owner.id:
        db.session.add(SpreadsheetPermission(spreadsheet_id=ss.id, user_id=old_owner.id, role='manager',
                                             granted_by=actor.id))
    record_activity(ss, actor, 'ownership', f'Transferred ownership to {new_owner.username}')


# ── Saving: batched operations ────────────────────────────────────────────

def _shift_cells(sheet_id: int, axis: str, at: int, delta: int):
    """Move every cell at row/col >= at by delta. Done via a negative
    staging range so the (sheet,row,col) unique key never collides."""
    col = SpreadsheetCell.row if axis == 'row' else SpreadsheetCell.col
    base = SpreadsheetCell.query.filter(SpreadsheetCell.sheet_id == sheet_id)
    base.filter(col >= at).update({col: -(col + delta) - 1}, synchronize_session=False)
    base.filter(col < 0).update({col: -col - 1}, synchronize_session=False)


def _resolve_sheet(ss: Spreadsheet, sheet_ref, id_map: dict) -> SpreadsheetSheet:
    sid = id_map.get(str(sheet_ref), sheet_ref)
    try:
        sid = int(sid)
    except (TypeError, ValueError):
        raise V.ValidationError('Unknown sheet.')
    sheet = SpreadsheetSheet.query.filter_by(id=sid, spreadsheet_id=ss.id).first()
    if not sheet:
        raise V.ValidationError('That sheet no longer exists. Reload the spreadsheet.')
    return sheet


def _unique_sheet_name(ss: Spreadsheet, wanted: str, exclude_id: Optional[int] = None) -> str:
    names = {s.name.lower() for s in ss.sheets.all() if s.id != exclude_id}
    name, n = wanted, 2
    while name.lower() in names:
        name = f'{wanted} ({n})'
        n += 1
    return name[:V.MAX_SHEET_NAME]


STRUCTURAL_OPS = {'insert_rows', 'delete_rows', 'insert_cols', 'delete_cols', 'replace_sheet', 'delete_sheet'}
CELL_OPS = {'set_cells'}


def _check_conflicts(ss: Spreadsheet, user, base_version: int, ops: list, id_map_preview: set):
    """Raise Conflict when applying `ops` on top of `base_version` would
    overwrite or misplace someone else's newer work."""
    if base_version >= ss.version:
        return
    # Layout (column widths, merges, filters...) is indexed by row/column
    # too, so it can't be applied on top of moved rows/columns either.
    touches_cells = any(op.get('op') in CELL_OPS | STRUCTURAL_OPS | {'sheet_props'} for op in ops)
    if touches_cells and ss.structure_version > base_version:
        last = (SpreadsheetActivity.query.filter(SpreadsheetActivity.spreadsheet_id == ss.id,
                                                 SpreadsheetActivity.user_id != user.id)
                .order_by(SpreadsheetActivity.updated_at.desc()).first())
        raise Conflict('Rows, columns or sheets were changed by another user since you loaded this spreadsheet.',
                       by=user_label(last.user) if last else None, structural=True)
    if any(op.get('op') in STRUCTURAL_OPS for op in ops):
        # A structural change of ours would move cells someone else just wrote.
        newer = (SpreadsheetCell.query.filter(SpreadsheetCell.spreadsheet_id == ss.id,
                                              SpreadsheetCell.version > base_version,
                                              SpreadsheetCell.updated_by != user.id).first())
        if newer:
            raise Conflict('Another user edited this spreadsheet while you were rearranging it.',
                           by=user_label(db.session.get(User, newer.updated_by)))
    for op in ops:
        if op.get('op') != 'set_cells' or str(op.get('sheet_id')) in id_map_preview:
            continue
        positions = [(c.get('r'), c.get('c')) for c in op.get('cells') or [] if isinstance(c, dict)]
        if not positions:
            continue
        try:
            sid = int(op.get('sheet_id'))
        except (TypeError, ValueError):
            continue
        wanted = set(positions)
        newer = (SpreadsheetCell.query.filter(SpreadsheetCell.sheet_id == sid,
                                              SpreadsheetCell.version > base_version,
                                              SpreadsheetCell.updated_by != user.id).all())
        clash = [c for c in newer if (c.row, c.col) in wanted]
        if clash:
            who = user_label(db.session.get(User, clash[0].updated_by))
            raise Conflict(f'{len(clash)} cell(s) you edited were changed by {who} at the same time.', by=who)


def apply_batch(ss: Spreadsheet, user, base_version: int, ops: list, force: bool = False) -> dict:
    """Apply a list of operations as ONE new version of the spreadsheet.

    Supported ops (sheet ids may be a temporary client id of a sheet added
    earlier in the same batch):
      set_cells     {sheet_id, cells:[{r,c,v,f}]}   full state of each cell
      insert_rows / delete_rows / insert_cols / delete_cols {sheet_id, at, count}
      replace_sheet {sheet_id, cells:[...]}         all cells of a sheet (sort, undo)
      sheet_props   {sheet_id, props, rows, cols, frozen_rows, frozen_cols}
      add_sheet     {client_id, name, position?, rows?, cols?, color?}
      duplicate_sheet {sheet_id, client_id, name}
      sheet_meta    {sheet_id, name?, color?, hidden?}
      move_sheets   {order:[sheet ids]}
      delete_sheet  {sheet_id}
    """
    if not isinstance(ops, list) or not ops:
        raise V.ValidationError('Nothing to save.')
    if len(ops) > 500:
        raise V.ValidationError('Too many changes in one save.')
    if not force:
        temp_ids = {str(op.get('client_id')) for op in ops if op.get('op') in ('add_sheet', 'duplicate_sheet')}
        _check_conflicts(ss, user, int(base_version or 0), ops, temp_ids)

    ss.version = (ss.version or 1) + 1
    version = ss.version
    now = datetime.utcnow()
    id_map, cell_count, actions = {}, 0, []
    total_cells = 0

    for op in ops:
        kind = op.get('op')
        if kind == 'set_cells':
            sheet = _resolve_sheet(ss, op.get('sheet_id'), id_map)
            cells = op.get('cells') or []
            total_cells += len(cells)
            if total_cells > 100000:
                raise V.ValidationError('Too many cells in one save.')
            positions = []
            clean = {}
            for item in cells:
                if not isinstance(item, dict):
                    continue
                r = V._int(item.get('r'), 0, V.MAX_ROWS - 1)
                c = V._int(item.get('c'), 0, V.MAX_COLS - 1)
                if r is None or c is None:
                    raise V.ValidationError('A cell is outside the sheet.')
                clean[(r, c)] = (V.clean_value(item.get('v')), V.dump(V.clean_fmt(item.get('f'))))
                positions.append((r, c))
            existing = {}
            for chunk_start in range(0, len(positions), 400):
                chunk = positions[chunk_start:chunk_start + 400]
                rows = sorted({p[0] for p in chunk})
                for cell in SpreadsheetCell.query.filter(SpreadsheetCell.sheet_id == sheet.id,
                                                         SpreadsheetCell.row.in_(rows)).all():
                    existing[(cell.row, cell.col)] = cell
            for (r, c), (value, fmt) in clean.items():
                cell = existing.get((r, c))
                if cell:
                    if cell.value == value and cell.fmt == fmt:
                        continue
                    cell.value, cell.fmt = value, fmt
                    cell.version, cell.updated_by, cell.updated_at = version, user.id, now
                elif value is not None or fmt is not None:
                    db.session.add(SpreadsheetCell(spreadsheet_id=ss.id, sheet_id=sheet.id, row=r, col=c,
                                                   value=value, fmt=fmt, version=version,
                                                   updated_by=user.id, updated_at=now))
                else:
                    continue
                cell_count += 1
            sheet.row_count = max(sheet.row_count, max((p[0] for p in positions), default=-1) + 1)
            sheet.col_count = max(sheet.col_count, max((p[1] for p in positions), default=-1) + 1)
            sheet.updated_at = now

        elif kind in ('insert_rows', 'delete_rows', 'insert_cols', 'delete_cols'):
            sheet = _resolve_sheet(ss, op.get('sheet_id'), id_map)
            axis = 'row' if kind.endswith('rows') else 'col'
            limit = V.MAX_ROWS if axis == 'row' else V.MAX_COLS
            at = V._int(op.get('at'), 0, limit)
            count = V._int(op.get('count'), 1, limit)
            if at is None or count is None:
                raise V.ValidationError('Invalid row/column position.')
            size_attr = 'row_count' if axis == 'row' else 'col_count'
            if kind.startswith('insert'):
                if getattr(sheet, size_attr) + count > limit:
                    raise V.ValidationError(f'A sheet can have at most {limit:,} {axis}s.')
                _shift_cells(sheet.id, axis, at, count)
                setattr(sheet, size_attr, getattr(sheet, size_attr) + count)
                actions.append(f'Inserted {count} {axis}(s) in {sheet.name}')
            else:
                col = SpreadsheetCell.row if axis == 'row' else SpreadsheetCell.col
                SpreadsheetCell.query.filter(SpreadsheetCell.sheet_id == sheet.id,
                                             col >= at, col < at + count).delete(synchronize_session=False)
                _shift_cells(sheet.id, axis, at + count, -count)
                setattr(sheet, size_attr, max(1, getattr(sheet, size_attr) - count))
                actions.append(f'Deleted {count} {axis}(s) in {sheet.name}')
            # Re-stamp moved cells so other clients reload them.
            SpreadsheetCell.query.filter(SpreadsheetCell.sheet_id == sheet.id).update(
                {SpreadsheetCell.version: version}, synchronize_session=False)
            ss.structure_version = version
            sheet.updated_at = now

        elif kind == 'replace_sheet':
            sheet = _resolve_sheet(ss, op.get('sheet_id'), id_map)
            cells = op.get('cells') or []
            if len(cells) > 200000:
                raise V.ValidationError('This sheet is too large to save in one go.')
            SpreadsheetCell.query.filter(SpreadsheetCell.sheet_id == sheet.id).delete(synchronize_session=False)
            max_r = max_c = -1
            for item in cells:
                if not isinstance(item, dict):
                    continue
                r = V._int(item.get('r'), 0, V.MAX_ROWS - 1)
                c = V._int(item.get('c'), 0, V.MAX_COLS - 1)
                if r is None or c is None:
                    continue
                value, fmt = V.clean_value(item.get('v')), V.dump(V.clean_fmt(item.get('f')))
                if value is None and fmt is None:
                    continue
                db.session.add(SpreadsheetCell(spreadsheet_id=ss.id, sheet_id=sheet.id, row=r, col=c,
                                               value=value, fmt=fmt, version=version,
                                               updated_by=user.id, updated_at=now))
                max_r, max_c = max(max_r, r), max(max_c, c)
            sheet.row_count = max(sheet.row_count, max_r + 1)
            sheet.col_count = max(sheet.col_count, max_c + 1)
            ss.structure_version = version
            sheet.updated_at = now
            actions.append(op.get('label') if isinstance(op.get('label'), str) else f'Rearranged {sheet.name}')

        elif kind == 'sheet_props':
            sheet = _resolve_sheet(ss, op.get('sheet_id'), id_map)
            if 'props' in op:
                sheet.props = V.dump(V.clean_props(op.get('props')))
            rows = V._int(op.get('rows'), 1, V.MAX_ROWS)
            cols = V._int(op.get('cols'), 1, V.MAX_COLS)
            if rows:
                sheet.row_count = rows
            if cols:
                sheet.col_count = cols
            fr = V._int(op.get('frozen_rows'), 0, 50)
            fc = V._int(op.get('frozen_cols'), 0, 26)
            if fr is not None:
                sheet.frozen_rows = fr
            if fc is not None:
                sheet.frozen_cols = fc
            sheet.props_version = version
            sheet.updated_at = now

        elif kind in ('add_sheet', 'duplicate_sheet'):
            client_id = str(op.get('client_id') or '')
            if not client_id:
                raise V.ValidationError('Missing sheet id.')
            if ss.sheets.count() >= 200:
                raise V.ValidationError('A spreadsheet can have at most 200 sheets.')
            name = _unique_sheet_name(ss, V.clean_name(op.get('name'), V.MAX_SHEET_NAME, 'Sheet name'))
            position = V._int(op.get('position'), 0, 1000)
            if position is None:
                position = (db.session.query(func.max(SpreadsheetSheet.position))
                            .filter_by(spreadsheet_id=ss.id).scalar() or 0) + 1
            if kind == 'duplicate_sheet':
                src = _resolve_sheet(ss, op.get('sheet_id'), id_map)
                sheet = SpreadsheetSheet(spreadsheet=ss, name=name, position=position, color=src.color,
                                         row_count=src.row_count, col_count=src.col_count,
                                         frozen_rows=src.frozen_rows, frozen_cols=src.frozen_cols,
                                         props=src.props, props_version=version)
                db.session.add(sheet)
                db.session.flush()
                copy_sheet_cells(ss, src, sheet, user.id)
                actions.append(f'Duplicated sheet {src.name}')
            else:
                sheet = _new_sheet(ss, name, position,
                                   V._int(op.get('rows'), 1, V.MAX_ROWS) or DEFAULT_ROWS,
                                   V._int(op.get('cols'), 1, V.MAX_COLS) or DEFAULT_COLS)
                sheet.color = V.color(op.get('color'))
                sheet.props_version = version
                db.session.flush()
                actions.append(f'Added sheet {name}')
            id_map[client_id] = sheet.id

        elif kind == 'sheet_meta':
            sheet = _resolve_sheet(ss, op.get('sheet_id'), id_map)
            if 'name' in op:
                new_name = V.clean_name(op.get('name'), V.MAX_SHEET_NAME, 'Sheet name')
                if new_name.lower() in {s.name.lower() for s in ss.sheets.all() if s.id != sheet.id}:
                    raise V.ValidationError(f'A sheet named "{new_name}" already exists.')
                if new_name != sheet.name:
                    actions.append(f'Renamed sheet {sheet.name} to {new_name}')
                sheet.name = new_name
            if 'color' in op:
                sheet.color = V.color(op.get('color'))
            if 'hidden' in op:
                hide = bool(op.get('hidden'))
                if hide and not sheet.is_hidden:
                    visible = [s for s in ss.sheets.all() if not s.is_hidden and s.id != sheet.id]
                    if not visible:
                        raise V.ValidationError('At least one sheet must stay visible.')
                sheet.is_hidden = hide
            sheet.props_version = version
            sheet.updated_at = now

        elif kind == 'move_sheets':
            order = op.get('order') or []
            sheets = {s.id: s for s in ss.sheets.all()}
            for pos, ref in enumerate(order):
                sid = id_map.get(str(ref), ref)
                try:
                    sid = int(sid)
                except (TypeError, ValueError):
                    continue
                if sid in sheets:
                    sheets[sid].position = pos
                    sheets[sid].props_version = version

        elif kind == 'delete_sheet':
            sheet = _resolve_sheet(ss, op.get('sheet_id'), id_map)
            if ss.sheets.count() <= 1:
                raise V.ValidationError('A spreadsheet must keep at least one sheet.')
            remaining_visible = [s for s in ss.sheets.all() if s.id != sheet.id and not s.is_hidden]
            if not remaining_visible:
                raise V.ValidationError('At least one visible sheet must remain.')
            SpreadsheetCell.query.filter_by(sheet_id=sheet.id).delete(synchronize_session=False)
            SpreadsheetPermission.query.filter_by(sheet_id=sheet.id).delete(synchronize_session=False)
            actions.append(f'Deleted sheet {sheet.name}')
            db.session.delete(sheet)
            ss.structure_version = version
        else:
            raise V.ValidationError('Unknown change type.')

    ss.updated_at = now
    ss.updated_by = user.id
    if cell_count:
        record_activity(ss, user, 'edit', 'Edited {n} cell(s)', count=cell_count, coalesce=True)
    for text in actions:
        record_activity(ss, user, 'structure', text)
    db.session.flush()
    return {'version': version, 'structure_version': ss.structure_version, 'id_map': id_map,
            'changes': changes_since(ss, int(base_version or 0), until=version, exclude_user=user.id)}


def changes_since(ss: Spreadsheet, since: int, until: Optional[int] = None,
                  exclude_user: Optional[int] = None) -> dict:
    """Everything other people changed after version `since`: cells, sheet
    layout and the sheet list. `reload` means coordinates moved and the
    client should reload rather than merge."""
    reload_needed = ss.structure_version > since
    out = {'version': ss.version, 'structure_version': ss.structure_version, 'reload': reload_needed,
           'sheets': [sheet_meta(s) for s in ss.sheets.all()], 'cells': {}, 'props': {},
           'updated_by': user_label(ss.updater) if ss.updated_by else None,
           'updated_at': iso(ss.updated_at), 'name': ss.name}
    if reload_needed or since >= ss.version:
        return out
    q = SpreadsheetCell.query.filter(SpreadsheetCell.spreadsheet_id == ss.id,
                                     SpreadsheetCell.version > since)
    if until is not None:
        q = q.filter(SpreadsheetCell.version < until)
    if exclude_user is not None:
        q = q.filter(or_(SpreadsheetCell.updated_by != exclude_user, SpreadsheetCell.updated_by.is_(None)))
    rows = q.limit(20001).all()
    if len(rows) > 20000:
        out['reload'] = True
        return out
    for c in rows:
        out['cells'].setdefault(str(c.sheet_id), []).append(cell_json(c))
    for s in ss.sheets.filter(SpreadsheetSheet.props_version > since).all():
        if until is not None and s.props_version >= until:
            continue
        out['props'][str(s.id)] = V.load(s.props, {}) or {}
    return out
