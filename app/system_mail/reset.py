"""Forgot-password logic: issue a one-time temporary password by email.

* The user's current password is never changed by a request; the temporary
  password is stored separately (hashed) and expires after RESET_MINUTES.
* The email shows the username and temporary password with a "Sign in"
  button. Signing in with them works once, then the new-password form opens.
* Requests are rate-limited per user and per IP address.
"""
import re
import secrets
from datetime import datetime, timedelta

from flask import render_template, url_for
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models import Company, User
from app.system_mail import mailer
from app.system_mail.models import PasswordReset

RESET_MINUTES = 30
USER_COOLDOWN_SECONDS = 60
USER_MAX_PER_HOUR = 5
IP_MAX_PER_15_MIN = 10

_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'  # no 0/O, 1/l/I
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class ResetError(Exception):
    """A user-facing reason the request could not be completed."""

    def __init__(self, message, category='error'):
        super().__init__(message)
        self.category = category


def valid_email(value):
    return bool(value and _EMAIL_RE.match(value.strip()))


def mask_email(email):
    """j***n@g***.com — enough for the user to recognise it."""
    local, _, domain = (email or '').partition('@')
    name, dot, tld = domain.rpartition('.')

    def m(part):
        if len(part) <= 2:
            return part[:1] + '*'
        return part[0] + '***' + part[-1]
    return f'{m(local)}@{m(name)}{dot}{tld}' if name else f'{m(local)}@{domain}'


def find_user(identifier):
    ident = (identifier or '').strip()
    if not ident:
        return None
    user = User.query.filter(User.username == ident).first()
    if user is None:
        user = User.query.filter(func.lower(User.email) == ident.lower()).first()
    return user


def generate_temp_password(length=12):
    """Random password with at least one upper, lower and digit."""
    while True:
        pw = ''.join(secrets.choice(_ALPHABET) for _ in range(length))
        if any(c.isupper() for c in pw) and any(c.islower() for c in pw) and any(c.isdigit() for c in pw):
            return pw


def _check_rate_limits(user, ip, now):
    if ip:
        recent_ip = PasswordReset.query.filter(PasswordReset.requested_ip == ip,
                                               PasswordReset.created_at >= now - timedelta(minutes=15)).count()
        if recent_ip >= IP_MAX_PER_15_MIN:
            raise ResetError('Too many password reset requests from this device. Please try again in 15 minutes.',
                             'warning')
    last = (PasswordReset.query.filter_by(user_id=user.id)
            .order_by(PasswordReset.created_at.desc()).first())
    if last and (now - last.created_at).total_seconds() < USER_COOLDOWN_SECONDS:
        wait = USER_COOLDOWN_SECONDS - int((now - last.created_at).total_seconds())
        raise ResetError(f'A temporary password was just sent to {mask_email(last.sent_to)}. '
                         f'Check your inbox (and spam folder), or try again in {wait} seconds.', 'warning')
    hourly = PasswordReset.query.filter(PasswordReset.user_id == user.id,
                                        PasswordReset.created_at >= now - timedelta(hours=1)).count()
    if hourly >= USER_MAX_PER_HOUR:
        raise ResetError('Too many password reset requests for this account. Please try again in an hour.',
                         'warning')


def request_reset(identifier, ip=None):
    """Validate, create the reset and email it. Returns the masked address.
    Raises ResetError with a message to show on any problem."""
    settings = mailer.get_settings()
    if not settings or not settings.is_configured:
        raise ResetError('Password reset by email is not set up yet. Please ask your administrator to '
                         'configure Settings > Email (SMTP).', 'warning')

    user = find_user(identifier)
    if user is None:
        raise ResetError('No user account was found with that username or email. Please check it and try again.')
    if not user.is_active:
        raise ResetError('This account is inactive. Please contact your administrator.', 'warning')
    email = (user.email or '').strip()
    if not valid_email(email):
        raise ResetError('This user does not have a valid email address on file, so a temporary password '
                         'cannot be sent. Please ask your administrator to add an email in User Management.')

    now = datetime.utcnow()
    _check_rate_limits(user, ip, now)

    temp_password = generate_temp_password()
    # Only the newest temporary password is valid.
    PasswordReset.query.filter(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None),
                               PasswordReset.revoked_at.is_(None)).update({'revoked_at': now})
    reset = PasswordReset(user_id=user.id, temp_password_hash=generate_password_hash(temp_password),
                          sent_to=email, requested_ip=ip, created_at=now,
                          expires_at=now + timedelta(minutes=RESET_MINUTES))
    db.session.add(reset)
    db.session.flush()

    company = Company.query.first()
    ctx = dict(user=user, temp_password=temp_password, minutes=RESET_MINUTES,
               company_name=(company.name if company and company.name else 'ERP Portal'),
               login_url=url_for('auth.login', _external=True))
    ok, message = mailer.send_email(
        email, f'Your temporary password for {ctx["company_name"]}',
        render_template('system_mail/email/temp_password.txt', **ctx),
        render_template('system_mail/email/temp_password.html', **ctx))
    if not ok:
        db.session.rollback()
        raise ResetError('The temporary password could not be emailed: ' + message +
                         ' Please contact your administrator.')
    db.session.commit()
    return mask_email(email)


def login_with_temp_password(username, password):
    """Return the user if ``password`` is their current, unexpired temporary
    password (and mark it used), else None."""
    user = User.query.filter_by(username=(username or '').strip()).first()
    if not user or not password:
        return None
    now = datetime.utcnow()
    reset = (PasswordReset.query
             .filter(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None),
                     PasswordReset.revoked_at.is_(None), PasswordReset.expires_at > now)
             .order_by(PasswordReset.created_at.desc()).first())
    if not reset or not check_password_hash(reset.temp_password_hash, password):
        return None
    reset.used_at = now
    db.session.commit()
    return user


def revoke_pending(user):
    """The user signed in with their real password: drop any outstanding
    temporary password so it can't be used later."""
    n = PasswordReset.query.filter(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None),
                                   PasswordReset.revoked_at.is_(None)).update({'revoked_at': datetime.utcnow()})
    if n:
        db.session.commit()

