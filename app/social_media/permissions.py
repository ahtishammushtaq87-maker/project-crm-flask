"""Who may do what in the Social Media module. Every route goes through
these helpers; hiding a button in the page is only cosmetic.

CRM admins (User.role == 'admin') have every permission. Everyone else gets
the union of their role's grants and their personal grants, both set by an
admin in Social Media > API Settings > Permissions. Nobody has anything by
default.
"""
from functools import wraps

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user

from app.social_media.models import (PERMISSION_FLAGS, SocialAccount, SocialAccountAccess, SocialRolePermission,
                                     SocialUserPermission)

FLAG_NAMES = [f for f, _ in PERMISSION_FLAGS]


def is_admin(user=None):
    user = user or current_user
    return bool(getattr(user, 'is_authenticated', False)) and getattr(user, 'role', '') == 'admin'


def perms_for(user=None):
    """dict flag -> bool for the user (cached on the user object per request)."""
    user = user or current_user
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', True):
        return {f: False for f in FLAG_NAMES}
    cached = getattr(user, '_sm_perms', None)
    if cached is not None:
        return cached
    if is_admin(user):
        result = {f: True for f in FLAG_NAMES}
    else:
        rows = [SocialRolePermission.query.get(getattr(user, 'role', None) or 'user'),
                SocialUserPermission.query.filter_by(user_id=user.id).first()]
        result = {f: any(bool(r and getattr(r, f)) for r in rows) for f in FLAG_NAMES}
        # Every other permission implies access to the module itself.
        if any(result.values()):
            result['can_view'] = True
    try:
        user._sm_perms = result
    except AttributeError:
        pass
    return result


def can(flag, user=None):
    return perms_for(user).get(flag, False)


def require(*flags):
    """Decorator: the user needs every listed flag. Pages redirect with a
    message; JSON endpoints and non-GET requests get 401/403."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.path.startswith('/social-media/api/'):
                    abort(401)
                return redirect(url_for('auth.login', next=request.url))
            if not all(can(f) for f in flags):
                if request.path.startswith('/social-media/api/') or request.method != 'GET':
                    abort(403)
                flash('You do not have permission to use this part of Social Media.', 'danger')
                return redirect(url_for('social_media.overview') if can('can_view')
                                else url_for('dashboard.index'))
            return fn(*args, **kwargs)
        return wrapper
    return deco


def visible_accounts(query=None, user=None):
    """Accounts the user may see/use: unrestricted accounts plus restricted
    ones they are listed on. Admins see everything."""
    user = user or current_user
    query = query if query is not None else SocialAccount.query
    if is_admin(user):
        return query
    restricted = SocialAccountAccess.query.with_entities(SocialAccountAccess.account_id).distinct()
    mine = SocialAccountAccess.query.with_entities(SocialAccountAccess.account_id).filter_by(user_id=user.id)
    return query.filter((~SocialAccount.id.in_(restricted)) | (SocialAccount.id.in_(mine)))


def can_use_account(account, user=None):
    if account is None:
        return False
    user = user or current_user
    return visible_accounts(SocialAccount.query.filter_by(id=account.id), user).first() is not None
