"""Routes: Forgot password / Change password (on /auth) and the admin
Settings > Email (SMTP) page (on /settings/email)."""
from datetime import datetime

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError, validate_csrf
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError

from app import db
from app.system_mail import mailer, reset as reset_service
from app.system_mail import reset_bp, settings_bp
from app.system_mail.forms import ChangePasswordForm, MailSettingsForm
from app.utils import log_activity

FORCE_CHANGE_KEY = 'must_change_password'


# ── Forgot / change password ───────────────────────────────────────────────

@reset_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """The "Forgot password?" button on the sign-in page posts the username
    typed there; the email goes straight to that user's address from User
    Management. There is no separate page: the result shows on sign-in."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    if request.method == 'GET':
        flash('Type your username in the sign-in form, then click "Forgot password?".', 'info')
        return redirect(url_for('auth.login'))

    try:
        validate_csrf(request.form.get('csrf_token'))
    except (ValidationError, CSRFError):
        flash('Your session expired. Please try again.', 'warning')
        return redirect(url_for('auth.login'))

    identifier = (request.form.get('username') or '').strip()[:120]
    if not identifier:
        flash('Type your username first, then click "Forgot password?".', 'warning')
        return redirect(url_for('auth.login'))
    try:
        masked = reset_service.request_reset(identifier, ip=request.remote_addr)
    except reset_service.ResetError as e:
        flash(str(e), e.category)
        log_activity('Auth', 'Password reset failed', f'Identifier: {identifier} - {e}')
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Password reset: database error')
        flash('Something went wrong. Please try again in a moment.', 'error')
    else:
        log_activity('Auth', 'Password reset requested', f'Temporary password emailed to {masked}')
        flash(f'We emailed your username and a temporary password to {masked}. Sign in with them '
              f'within {reset_service.RESET_MINUTES} minutes, then set your new password.', 'success')
    return redirect(url_for('auth.login'))


@reset_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    forced = bool(session.get(FORCE_CHANGE_KEY))
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not forced and not current_user.check_password(form.current_password.data or ''):
            form.current_password.errors.append('Your current password is not correct.')
        else:
            current_user.set_password(form.new_password.data)
            try:
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                current_app.logger.exception('Change password: database error')
                flash('Your password could not be saved. Please try again.', 'error')
            else:
                session.pop(FORCE_CHANGE_KEY, None)
                log_activity('Auth', 'Password changed', 'After temporary password' if forced else 'By user')
                flash('Your password has been changed.', 'success')
                return redirect(url_for('dashboard.index'))
    return render_template('system_mail/change_password.html', form=form, forced=forced)


def enforce_password_change():
    """After signing in with a temporary password, keep the user on the
    change-password page until they choose a new one."""
    if not session.get(FORCE_CHANGE_KEY) or not current_user.is_authenticated:
        return None
    if request.endpoint in ('password_reset.change_password', 'auth.logout', 'static') or request.endpoint is None:
        return None
    return redirect(url_for('password_reset.change_password'))


# ── Settings > Email (SMTP) ────────────────────────────────────────────────

def _admin_required():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.url))
    if not current_user.is_admin:
        flash('Only administrators can change email settings.', 'danger')
        return redirect(url_for('dashboard.index'))
    return None


def _config_from_form(form, saved):
    """Values to test with: the form as typed; a blank password field means
    "keep the saved password"."""
    password = form.smtp_password.data or (saved.smtp_password if saved else '')
    return mailer.SmtpConfig(form.smtp_host.data, form.smtp_port.data, form.security.data,
                             form.smtp_username.data, password, form.from_email.data,
                             form.from_name.data, form.reply_to.data, form.timeout_seconds.data or 20)


def _record_test(saved, ok, message):
    if saved is None or saved.id is None:
        return
    saved.last_test_at = datetime.utcnow()
    saved.last_test_ok = ok
    saved.last_test_message = message[:500]
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()


@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def email_settings():
    denied = _admin_required()
    if denied:
        return denied
    saved = mailer.get_settings()
    form = MailSettingsForm(obj=saved) if request.method == 'GET' else MailSettingsForm()
    if request.method == 'GET':
        form.smtp_password.data = ''
        if saved is None:
            form.smtp_port.data = 587
            form.security.data = 'starttls'
            form.timeout_seconds.data = 20
        form.test_to.data = current_user.email or ''

    action = request.form.get('action', 'save')
    if request.method == 'POST' and form.validate_on_submit():
        if action in ('test_connection', 'send_test'):
            cfg = _config_from_form(form, saved)
            if action == 'test_connection':
                ok, message = mailer.test_connection(cfg)
            else:
                to = (form.test_to.data or '').strip()
                if not to:
                    form.test_to.errors.append('Enter the address to send the test email to.')
                    return render_template('system_mail/settings.html', form=form, saved=saved)
                ok, message = mailer.send_email(
                    to, 'Test email from your CRM',
                    render_template('system_mail/email/test.txt', sent_by=current_user.username),
                    render_template('system_mail/email/test.html', sent_by=current_user.username),
                    cfg=cfg)
            _record_test(saved, ok, message)
            log_activity('Settings', 'Email settings test', f'{action}: {"OK" if ok else "failed"} - {message}')
            flash(message if ok else f'Test failed: {message}', 'success' if ok else 'danger')
            return render_template('system_mail/settings.html', form=form, saved=saved)

        settings = mailer.get_settings(create=True)
        settings.is_enabled = bool(form.is_enabled.data)
        settings.smtp_host = form.smtp_host.data.strip()
        settings.smtp_port = form.smtp_port.data
        settings.security = form.security.data
        settings.smtp_username = (form.smtp_username.data or '').strip() or None
        if form.smtp_password.data:
            settings.smtp_password = form.smtp_password.data
        if request.form.get('clear_password') == '1':
            settings.smtp_password = None
        settings.from_email = form.from_email.data.strip()
        settings.from_name = (form.from_name.data or '').strip() or None
        settings.reply_to = (form.reply_to.data or '').strip() or None
        settings.timeout_seconds = form.timeout_seconds.data or 20
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception('Email settings: save failed')
            flash('The email settings could not be saved. Please try again.', 'danger')
            return render_template('system_mail/settings.html', form=form, saved=saved)
        log_activity('Settings', 'Updated email (SMTP) settings',
                     f'{settings.smtp_host}:{settings.smtp_port} ({settings.security}), enabled={settings.is_enabled}')
        flash('Email settings saved.' + ('' if settings.is_enabled else
                                         ' Email sending is turned off until you enable it.'), 'success')
        return redirect(url_for('system_mail.email_settings'))
    elif request.method == 'POST':
        flash('Please correct the highlighted fields.', 'danger')
    return render_template('system_mail/settings.html', form=form, saved=saved)
