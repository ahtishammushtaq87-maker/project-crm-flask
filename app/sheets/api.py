"""JSON API for the Spreadsheet module (mounted under /sheets/api).

Every endpoint goes through ``api_endpoint``, which:
  * returns 401 JSON (not a login redirect) when the session has expired,
  * checks the CSRF token on every request that changes something,
  * turns validation problems, conflicts and permission failures into
    friendly JSON messages, and logs anything unexpected server-side
    without exposing details to the browser.
Access to a specific spreadsheet is always checked with ``load_book``.
"""
from functools import wraps

from flask import jsonify, request, current_app, send_file
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError as CSRFError
import io as _io
import re

from app import db
from app.models import User
from app.utils import log_activity
from app.sheets import bp, services as S, permissions as P, validators as V, io as sheet_io
from app.sheets.models import Spreadsheet, SpreadsheetSheet, SpreadsheetCell, SpreadsheetPermission
from app.sheets.starter_templates import template_choices


class ApiError(Exception):
    def __init__(self, status: int, message: str, **extra):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra


def api_endpoint(rule, methods=('GET',)):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify(ok=False, error='Your session has expired. Sign in again.', code='auth'), 401
            if not getattr(current_user, 'is_active', True):
                return jsonify(ok=False, error='Your account is disabled.', code='auth'), 403
            if request.method not in ('GET', 'HEAD', 'OPTIONS'):
                try:
                    validate_csrf(request.headers.get('X-CSRFToken') or request.form.get('csrf_token'))
                except CSRFError:
                    return jsonify(ok=False, error='Your session has expired. Reload the page and try again.',
                                   code='csrf'), 400
            try:
                return fn(*args, **kwargs)
            except ApiError as e:
                db.session.rollback()
                return jsonify(ok=False, error=e.message, **e.extra), e.status
            except V.ValidationError as e:
                db.session.rollback()
                return jsonify(ok=False, error=str(e)), 400
            except sheet_io.ImportError_ as e:
                db.session.rollback()
                return jsonify(ok=False, error=str(e)), 400
            except S.Conflict as e:
                db.session.rollback()
                return jsonify(ok=False, error=str(e), code='conflict', by=e.by, structural=e.structural), 409
            except Exception:
                db.session.rollback()
                current_app.logger.exception('Spreadsheet API error on %s', request.path)
                return jsonify(ok=False, error='Something went wrong. Your last change was not saved.'), 500
        endpoint = 'api_' + fn.__name__
        bp.add_url_rule('/api' + rule, endpoint, wrapper, methods=list(methods))
        return wrapper
    return decorator


def body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def load_book(book_id: int, need: str = 'view', allow_deleted: bool = False):
    """The spreadsheet plus the caller's role, or a 404/403 ApiError.
    No-access answers 404 for spreadsheets the user can't see at all, so
    ids can't be probed."""
    ss = db.session.get(Spreadsheet, book_id)
    if not ss or (ss.is_deleted and not allow_deleted):
        raise ApiError(404, 'Spreadsheet not found.')
    role = P.role_for(current_user, ss)
    if not P.can_view(role):
        raise ApiError(404, 'Spreadsheet not found.')
    checks = {'view': P.can_view, 'edit': P.can_edit, 'share': P.can_share,
              'settings': P.can_manage_settings, 'delete': P.can_delete, 'transfer': P.can_transfer,
              'export': lambda r: P.can_export(r, ss)}
    if not checks[need](role):
        messages = {'edit': 'You have view-only access to this spreadsheet.',
                    'share': 'You do not have permission to share this spreadsheet.',
                    'settings': 'You do not have permission to change this spreadsheet\'s settings.',
                    'delete': 'Only the owner can delete this spreadsheet.',
                    'transfer': 'Only the owner can transfer ownership.',
                    'export': 'The owner has not allowed viewers to download this spreadsheet.'}
        raise ApiError(403, messages.get(need, 'You do not have permission to do that.'))
    return ss, role


def book_payload(ss, role) -> dict:
    data = S.summary(ss, current_user, S.user_state(ss, current_user), role=role)
    data.update(version=ss.version, structure_version=ss.structure_version,
                viewers_can_export=bool(ss.viewers_can_export),
                can=P.capabilities(role, ss),
                sheets=[S.sheet_meta(s) for s in ss.sheets.all()])
    return data


# ── Spreadsheets ─────────────────────────────────────────────────────────

@api_endpoint('/spreadsheets')
def list_spreadsheets():
    scope = request.args.get('scope', 'all')
    if scope in ('admin_all', 'deleted') and not P.is_crm_admin(current_user):
        raise ApiError(403, 'Only administrators can see every spreadsheet.')
    items = S.list_for_user(current_user, request.args.get('q', ''), request.args.get('sort', 'modified'), scope)
    recent = []
    if scope == 'all' and not request.args.get('q'):
        recent = sorted([i for i in items if i['last_opened_at']], key=lambda i: i['last_opened_at'],
                        reverse=True)[:6]
    return jsonify(ok=True, items=items, recent=recent, is_admin=P.is_crm_admin(current_user))


@api_endpoint('/templates')
def list_templates():
    return jsonify(ok=True, templates=template_choices())


@api_endpoint('/spreadsheets', methods=('POST',))
def create_spreadsheet():
    data = body()
    ss = S.create_spreadsheet(current_user, data.get('name'), data.get('description') or '',
                              data.get('template') or 'blank')
    S.mark_opened(ss, current_user)
    db.session.commit()
    log_activity('Spreadsheet', f'Created spreadsheet: {ss.name}', f'Spreadsheet #{ss.id}')
    return jsonify(ok=True, id=ss.id, item=S.summary(ss, current_user, role='owner'))


@api_endpoint('/spreadsheets/<int:book_id>')
def get_spreadsheet(book_id):
    ss, role = load_book(book_id)
    S.mark_opened(ss, current_user)
    db.session.commit()
    return jsonify(ok=True, book=book_payload(ss, role))


@api_endpoint('/spreadsheets/<int:book_id>', methods=('PATCH',))
def update_spreadsheet(book_id):
    ss, role = load_book(book_id, 'settings')
    data = body()
    changes = []
    if 'name' in data:
        name = V.clean_name(data.get('name'))
        if name != ss.name:
            changes.append(f'Renamed "{ss.name}" to "{name}"')
            ss.name = name
    if 'description' in data:
        ss.description = (V._text(data.get('description'), 2000) or '').strip() or None
        changes.append('Updated description')
    if 'viewers_can_export' in data:
        if not P.can_delete(role):
            raise ApiError(403, 'Only the owner can change download settings.')
        ss.viewers_can_export = bool(data.get('viewers_can_export'))
        changes.append('Viewers ' + ('can' if ss.viewers_can_export else 'cannot') + ' download')
    for text in changes:
        S.record_activity(ss, current_user, 'settings', text)
    db.session.commit()
    if changes:
        log_activity('Spreadsheet', f'Updated spreadsheet: {ss.name}', '; '.join(changes))
    return jsonify(ok=True, book=book_payload(ss, role))


@api_endpoint('/spreadsheets/<int:book_id>', methods=('DELETE',))
def delete_spreadsheet(book_id):
    ss, _ = load_book(book_id, 'delete')
    S.soft_delete(ss, current_user)
    db.session.commit()
    log_activity('Spreadsheet', f'Deleted spreadsheet: {ss.name}', f'Spreadsheet #{ss.id}')
    return jsonify(ok=True)


@api_endpoint('/spreadsheets/<int:book_id>/restore', methods=('POST',))
def restore_spreadsheet(book_id):
    if not P.is_crm_admin(current_user):
        raise ApiError(403, 'Only administrators can restore deleted spreadsheets.')
    ss, _ = load_book(book_id, allow_deleted=True)
    S.restore(ss, current_user)
    db.session.commit()
    log_activity('Spreadsheet', f'Restored spreadsheet: {ss.name}', f'Spreadsheet #{ss.id}')
    return jsonify(ok=True)


@api_endpoint('/spreadsheets/<int:book_id>/duplicate', methods=('POST',))
def duplicate_spreadsheet(book_id):
    src, _ = load_book(book_id, 'view')
    copy = S.duplicate_spreadsheet(current_user, src, body().get('name'))
    db.session.commit()
    log_activity('Spreadsheet', f'Duplicated spreadsheet: {src.name}', f'New spreadsheet #{copy.id}')
    return jsonify(ok=True, id=copy.id, item=S.summary(copy, current_user, role='owner'))


@api_endpoint('/spreadsheets/<int:book_id>/favorite', methods=('POST',))
def favorite_spreadsheet(book_id):
    ss, _ = load_book(book_id)
    state = S.user_state(ss, current_user)
    state.is_favorite = bool(body().get('favorite'))
    db.session.commit()
    return jsonify(ok=True, favorite=state.is_favorite)


# ── Sheet data & saving ──────────────────────────────────────────────────

@api_endpoint('/spreadsheets/<int:book_id>/sheets/<int:sheet_id>')
def get_sheet(book_id, sheet_id):
    ss, _ = load_book(book_id)
    sheet = SpreadsheetSheet.query.filter_by(id=sheet_id, spreadsheet_id=ss.id).first()
    if not sheet:
        raise ApiError(404, 'That sheet no longer exists.')
    return jsonify(ok=True, version=ss.version, sheet=S.sheet_full(sheet))


@api_endpoint('/spreadsheets/<int:book_id>/batch', methods=('POST',))
def save_batch(book_id):
    ss, _ = load_book(book_id, 'edit')
    data = body()
    try:
        base_version = int(data.get('base_version'))
    except (TypeError, ValueError):
        raise ApiError(400, 'Reload the spreadsheet and try again.')
    result = S.apply_batch(ss, current_user, base_version, data.get('ops'), force=bool(data.get('force')))
    db.session.commit()
    return jsonify(ok=True, **result)


@api_endpoint('/spreadsheets/<int:book_id>/changes')
def get_changes(book_id):
    ss, role = load_book(book_id)
    since = request.args.get('since', type=int) or 0
    changes = S.changes_since(ss, since)
    changes['can'] = P.capabilities(role, ss)
    return jsonify(ok=True, **changes)


@api_endpoint('/spreadsheets/<int:book_id>/history')
def get_history(book_id):
    ss, _ = load_book(book_id)
    return jsonify(ok=True, items=S.history(ss))


# ── Sharing ──────────────────────────────────────────────────────────────

@api_endpoint('/spreadsheets/<int:book_id>/permissions')
def get_permissions(book_id):
    ss, role = load_book(book_id)
    return jsonify(ok=True, owner_id=ss.owner_id, items=S.permissions_list(ss), can=P.capabilities(role, ss))


def _target_user(user_id) -> User:
    try:
        user = db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        user = None
    if not user:
        raise ApiError(404, 'User not found.')
    return user


@api_endpoint('/spreadsheets/<int:book_id>/permissions', methods=('POST',))
def share_spreadsheet(book_id):
    ss, role = load_book(book_id, 'share')
    data = body()
    target = _target_user(data.get('user_id'))
    new_role = data.get('role')
    if new_role not in SpreadsheetPermission.ROLES:
        raise ApiError(400, 'Choose Viewer, Editor or Manager.')
    if target.id == ss.owner_id:
        raise ApiError(400, f'{target.username} already owns this spreadsheet.')
    if not target.is_active:
        raise ApiError(400, f'{target.username}\'s account is disabled.')
    existing = SpreadsheetPermission.query.filter_by(spreadsheet_id=ss.id, user_id=target.id, sheet_id=None).first()
    if not P.can_grant(role, new_role) or (existing and not P.can_revoke(role, existing.role)):
        raise ApiError(403, 'Only the owner can add or change managers.')
    S.set_permission(ss, current_user, target, new_role)
    db.session.commit()
    log_activity('Spreadsheet', f'Shared spreadsheet: {ss.name}', f'{target.username} as {new_role}')
    return jsonify(ok=True, items=S.permissions_list(ss))


@api_endpoint('/spreadsheets/<int:book_id>/permissions/<int:user_id>', methods=('DELETE',))
def revoke_access(book_id, user_id):
    ss, role = load_book(book_id)
    perm = SpreadsheetPermission.query.filter_by(spreadsheet_id=ss.id, user_id=user_id, sheet_id=None).first()
    if not perm:
        raise ApiError(404, 'That person does not have access.')
    leaving = user_id == current_user.id
    if not leaving and not (P.can_share(role) and P.can_revoke(role, perm.role)):
        raise ApiError(403, 'You do not have permission to remove this person.')
    name = perm.user.username
    db.session.delete(perm)
    S.record_activity(ss, current_user, 'unshared', f'{name} left' if leaving else f'Removed access for {name}')
    db.session.commit()
    log_activity('Spreadsheet', f'Removed spreadsheet access: {ss.name}', name)
    return jsonify(ok=True, items=S.permissions_list(ss) if not leaving else [])


@api_endpoint('/spreadsheets/<int:book_id>/transfer', methods=('POST',))
def transfer(book_id):
    ss, _ = load_book(book_id, 'transfer')
    target = _target_user(body().get('user_id'))
    if not target.is_active:
        raise ApiError(400, f'{target.username}\'s account is disabled.')
    if target.id == ss.owner_id:
        raise ApiError(400, f'{target.username} already owns this spreadsheet.')
    S.transfer_ownership(ss, current_user, target)
    db.session.commit()
    log_activity('Spreadsheet', f'Transferred spreadsheet: {ss.name}', f'New owner: {target.username}')
    return jsonify(ok=True, items=S.permissions_list(ss))


@api_endpoint('/users')
def find_users():
    return jsonify(ok=True, items=S.search_users(request.args.get('q', '')))


# ── Import / export ──────────────────────────────────────────────────────

@api_endpoint('/import/preview', methods=('POST',))
def import_preview():
    upload = request.files.get('file')
    if not upload or not upload.filename:
        raise ApiError(400, 'Choose a file to import.')
    sheets = sheet_io.parse_upload(upload.filename, upload.read())
    token = sheet_io.store(current_user.id, upload.filename, sheets)
    return jsonify(ok=True, token=token, filename=upload.filename, sheets=sheet_io.preview(sheets))


@api_endpoint('/import/confirm', methods=('POST',))
def import_confirm():
    data = body()
    parsed = sheet_io.load(data.get('token'), current_user.id)
    sheets = parsed['sheets']
    chosen = data.get('sheets')
    if isinstance(chosen, list) and chosen:
        wanted = {int(x) for x in chosen if str(x).isdigit()}
        sheets = [s for i, s in enumerate(sheets) if i in wanted]
    if not sheets:
        raise ApiError(400, 'Choose at least one sheet to import.')
    target_id = data.get('spreadsheet_id')
    if target_id:
        ss, _ = load_book(int(target_id), 'edit')
        added = S.add_imported_sheets(ss, current_user, sheets)
        action = f'Imported {len(added)} sheet(s) into {ss.name}'
    else:
        name = data.get('name') or re.sub(r'\.[^.]+$', '', parsed.get('filename') or 'Imported')
        ss = S.create_from_import(current_user, name, sheets)
        added = ss.sheets.all()
        action = f'Imported spreadsheet: {ss.name}'
    db.session.commit()
    sheet_io.discard(data.get('token'))
    log_activity('Spreadsheet', action, parsed.get('filename'))
    return jsonify(ok=True, id=ss.id, sheet_ids=[s.id for s in added])


@api_endpoint('/spreadsheets/<int:book_id>/export.xlsx')
def export_xlsx(book_id):
    ss, _ = load_book(book_id, 'export')
    sheets = ss.sheets.all()
    by_sheet = {s.id: [] for s in sheets}
    for c in SpreadsheetCell.query.filter(SpreadsheetCell.spreadsheet_id == ss.id).all():
        if c.sheet_id in by_sheet and (c.value is not None or c.fmt is not None):
            by_sheet[c.sheet_id].append(c)
    data = sheet_io.export_xlsx(ss, [(s, by_sheet[s.id]) for s in sheets])
    filename = re.sub(r'[^\w\- ]+', '_', ss.name).strip() or 'spreadsheet'
    return send_file(_io.BytesIO(data), as_attachment=True, download_name=f'{filename}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
