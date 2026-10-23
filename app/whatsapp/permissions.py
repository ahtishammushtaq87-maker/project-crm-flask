"""Who may do what in the WhatsApp module. Every route and API endpoint goes
through these helpers; hiding a button in the page is only cosmetic.

CRM admins (User.role == 'admin') have every permission. Everyone else has
none until an admin grants them in WhatsApp > Settings > Staff Permissions.
"""
from functools import wraps

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user

from app.whatsapp.models import WhatsAppConversation, WhatsAppUserPermission

FLAG_NAMES = [f for f, _ in WhatsAppUserPermission.FLAGS]


def is_admin(user=None):
    user = user or current_user
    return bool(getattr(user, 'is_authenticated', False)) and getattr(user, 'role', '') == 'admin'


def perms_for(user=None):
    """dict flag -> bool for the user (cached on the user object per request)."""
    user = user or current_user
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', True):
        return {f: False for f in FLAG_NAMES}
    cached = getattr(user, '_wa_perms', None)
    if cached is not None:
        return cached
    if is_admin(user):
        result = {f: True for f in FLAG_NAMES}
    else:
        row = WhatsAppUserPermission.query.filter_by(user_id=user.id).first()
        result = {f: bool(row and getattr(row, f)) for f in FLAG_NAMES}
        # Every other permission implies access to the module itself.
        if any(result.values()):
            result['can_view'] = True
    try:
        user._wa_perms = result
    except AttributeError:
        pass
    return result


def can(flag, user=None):
    return perms_for(user).get(flag, False)


def require(flag):
    """Decorator for pages (redirect) and JSON endpoints (403)."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.path.startswith('/whatsapp/api/'):
                    abort(401)
                return redirect(url_for('auth.login', next=request.url))
            if not can(flag):
                if request.path.startswith('/whatsapp/api/') or request.method != 'GET':
                    abort(403)
                flash('You do not have permission to use this part of WhatsApp.', 'danger')
                return redirect(url_for('whatsapp.dashboard') if can('can_view') else url_for('dashboard.index'))
            return fn(*args, **kwargs)
        return wrapper
    return deco


def visible_conversations(query=None, user=None):
    """Restrict a conversation query to what the user may see: everything
    with can_view_all, otherwise only conversations assigned to them."""
    user = user or current_user
    query = query if query is not None else WhatsAppConversation.query
    if can('can_view_all', user):
        return query
    return query.filter(WhatsAppConversation.assigned_to_id == user.id)


def can_see_conversation(conv, user=None):
    user = user or current_user
    if conv is None or not can('can_view', user):
        return False
    return can('can_view_all', user) or conv.assigned_to_id == user.id
