from flask import flash, redirect, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFError, validate_csrf
from wtforms.validators import ValidationError

from app import db
from app.impersonation import SESSION_KEY, bp
from app.models import User
from app.utils import log_activity

_FORCE_CHANGE_KEY = 'must_change_password'   # see app/system_mail/routes.py


def _state():
    data = session.get(SESSION_KEY)
    if isinstance(data, dict) and data.get('admin_id') and data.get('user_id'):
        return data
    return None


def is_impersonating():
    data = _state()
    return bool(data and current_user.is_authenticated and current_user.id == data['user_id'])


def can_impersonate(admin, target):
    """(allowed, reason) — the same rule for the button and the route."""
    if not getattr(admin, 'is_authenticated', False) or admin.role != 'admin':
        return False, 'Only administrators can sign in as another user.'
    if is_impersonating():
        return False, 'Return to your own account first.'
    if target is None:
        return False, 'User not found.'
    if target.id == admin.id:
        return False, 'That is your own account.'
    if target.role == 'admin':
        return False, 'You cannot sign in as another administrator.'
    if not target.is_active:
        return False, 'This user is inactive. Activate the account first.'
    return True, ''


def _csrf_ok():
    try:
        validate_csrf(request.form.get('csrf_token'))
        return True
    except (ValidationError, CSRFError):
        return False


@bp.route('/<int:user_id>/start', methods=['POST'])
@login_required
def start(user_id):
    target = db.session.get(User, user_id)
    if not _csrf_ok():
        flash('Your session expired. Please try again.', 'warning')
        return redirect(url_for('users.list_users'))
    allowed, reason = can_impersonate(current_user, target)
    if not allowed:
        flash(reason, 'danger')
        return redirect(url_for('users.list_users') if current_user.role == 'admin' else url_for('dashboard.index'))

    admin_id, admin_name = current_user.id, current_user.username
    log_activity('Users', f'Signed in as user {target.username}', f'Admin {admin_name} started testing as this user')
    login_user(target)
    session.pop(_FORCE_CHANGE_KEY, None)
    session[SESSION_KEY] = {'admin_id': admin_id, 'user_id': target.id}
    flash(f'You are now signed in as {target.username}. Use "Return to admin" in the top bar to switch back.', 'info')
    return redirect(url_for('dashboard.index'))


@bp.route('/stop', methods=['POST'])
@login_required
def stop():
    data = _state()
    if not is_impersonating():
        session.pop(SESSION_KEY, None)
        return redirect(url_for('dashboard.index'))
    if not _csrf_ok():
        flash('Your session expired. Please try again.', 'warning')
        return redirect(request.referrer or url_for('dashboard.index'))

    admin = db.session.get(User, data['admin_id'])
    viewed_name = current_user.username
    session.pop(SESSION_KEY, None)
    if admin is None or admin.role != 'admin' or not admin.is_active:
        # The admin account changed meanwhile: don't restore it.
        logout_user()
        flash('Your administrator account is no longer available. Please sign in again.', 'warning')
        return redirect(url_for('auth.login'))
    login_user(admin)
    log_activity('Users', f'Returned from user {viewed_name}', f'Admin {admin.username} stopped testing as this user')
    flash(f'Welcome back, {admin.username}. You have left {viewed_name}\'s account.', 'success')
    return redirect(url_for('users.list_users'))


def guard_session():
    """Drop a stale impersonation record (after logout / another sign-in)."""
    data = session.get(SESSION_KEY)
    if data is None:
        return None
    if request.endpoint == 'auth.logout' or not isinstance(data, dict) or \
            not current_user.is_authenticated or current_user.id != data.get('user_id'):
        session.pop(SESSION_KEY, None)
    return None


def inject_banner():
    if not is_impersonating():
        return {'impersonation': None}
    admin = db.session.get(User, _state()['admin_id'])
    return {'impersonation': {
        'admin_name': admin.username if admin else 'administrator',
        'user_name': current_user.username,
        'user_role': (current_user.role or 'user').capitalize(),
    }}
