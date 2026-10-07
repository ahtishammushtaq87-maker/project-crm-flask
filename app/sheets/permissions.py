"""Who may do what with a spreadsheet. Every page and API endpoint goes
through these helpers - the browser's view of permissions is only cosmetic.

Roles, strongest first:
  admin    CRM administrator (User.role == 'admin'): full control of every
           spreadsheet, including ones they don't own.
  owner    the spreadsheet's owner: full control.
  manager  edit + share with others (viewer/editor) + remove those people.
  editor   view + edit cells, formatting, rows/columns and sheets.
  viewer   open, search, filter; export only if the owner allows it.
"""
from typing import Optional

from app.sheets.models import Spreadsheet, SpreadsheetPermission

ROLE_RANK = {'viewer': 1, 'editor': 2, 'manager': 3, 'owner': 4, 'admin': 5}
ROLE_LABELS = {'viewer': 'Viewer', 'editor': 'Editor', 'manager': 'Manager', 'owner': 'Owner', 'admin': 'Admin'}


def is_crm_admin(user) -> bool:
    return bool(getattr(user, 'is_authenticated', False)) and getattr(user, 'role', '') == 'admin'


def role_for(user, spreadsheet: Optional[Spreadsheet]) -> Optional[str]:
    """The user's effective role on the spreadsheet, or None (no access).
    A deleted spreadsheet is only reachable by an admin."""
    if spreadsheet is None or not getattr(user, 'is_authenticated', False):
        return None
    if not getattr(user, 'is_active', True):
        return None
    if is_crm_admin(user):
        return 'admin'
    if spreadsheet.is_deleted:
        return None
    if spreadsheet.owner_id == user.id:
        return 'owner'
    perm = SpreadsheetPermission.query.filter_by(
        spreadsheet_id=spreadsheet.id, user_id=user.id, sheet_id=None).first()
    return perm.role if perm and perm.role in SpreadsheetPermission.ROLES else None


def _at_least(role: Optional[str], minimum: str) -> bool:
    return role is not None and ROLE_RANK.get(role, 0) >= ROLE_RANK[minimum]


def can_view(role: Optional[str]) -> bool:
    return _at_least(role, 'viewer')


def can_edit(role: Optional[str]) -> bool:
    return _at_least(role, 'editor')


def can_share(role: Optional[str]) -> bool:
    return _at_least(role, 'manager')


def can_manage_settings(role: Optional[str]) -> bool:
    """Rename, description, viewer-export setting."""
    return _at_least(role, 'manager')


def can_delete(role: Optional[str]) -> bool:
    return _at_least(role, 'owner')


def can_transfer(role: Optional[str]) -> bool:
    return _at_least(role, 'owner')


def can_export(role: Optional[str], spreadsheet: Spreadsheet) -> bool:
    if _at_least(role, 'editor'):
        return True
    return role == 'viewer' and bool(spreadsheet.viewers_can_export)


def can_grant(actor_role: Optional[str], target_role: str) -> bool:
    """Managers may hand out viewer/editor; owner/admin may also make managers."""
    if target_role not in SpreadsheetPermission.ROLES:
        return False
    if _at_least(actor_role, 'owner'):
        return True
    return actor_role == 'manager' and target_role in ('viewer', 'editor')


def can_revoke(actor_role: Optional[str], existing_role: str) -> bool:
    return can_grant(actor_role, existing_role)


def capabilities(role: Optional[str], spreadsheet: Spreadsheet) -> dict:
    """What the editor UI should offer (enforced again on every request)."""
    return {
        'role': role,
        'role_label': ROLE_LABELS.get(role, ''),
        'view': can_view(role),
        'edit': can_edit(role),
        'share': can_share(role),
        'settings': can_manage_settings(role),
        'delete': can_delete(role),
        'transfer': can_transfer(role),
        'export': can_export(role, spreadsheet),
        'grant_manager': can_grant(role, 'manager'),
    }
