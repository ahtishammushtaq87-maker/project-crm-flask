"""Shared helpers: settings, timezone, audit log, notifications, public URLs
and SQLite-lock-tolerant commits."""
import os
import time
from datetime import date, datetime, timedelta, timezone

from flask import has_request_context, request
from sqlalchemy.exc import OperationalError

from app import db
from app.social_media.models import SocialAuditLog, SocialNotification, SocialSetting
from app.social_media.services import security


def _linkedin_default_version():
    """LinkedIn versions are YYYYMM and each is supported for about a year.
    Default to the version from three months ago (new versions can lag)."""
    d = date.today().replace(day=1) - timedelta(days=80)
    return d.strftime('%Y%m')


# key -> default. Secret keys are listed in SECRET_KEYS.
DEFAULTS = {
    'enabled': '1',
    'timezone': 'Asia/Karachi',
    'default_status': 'draft',
    'default_account_ids': '',
    'max_image_mb': '8',
    'max_video_mb': '16',
    'allowed_image_types': 'image/jpeg,image/png',
    'allowed_video_types': 'video/mp4,video/quicktime',
    'max_retries': '3',
    'retry_base_seconds': '120',
    'public_base_url': '',
    'public_media_hours': '72',
    'media_cleanup_days': '0',
    'notify_success': '1',
    'notify_failure': '1',
    'notify_email_failures': '0',
    'notify_email_to': '',
    # Meta
    'meta_app_id': '',
    'meta_graph_version': 'v24.0',
    'meta_login_config_id': '',
    'meta_instagram_mode': 'facebook_login',
    'meta_scopes': 'pages_show_list,pages_read_engagement,pages_manage_posts,read_insights,business_management,'
                   'instagram_basic,instagram_content_publish,instagram_manage_insights',
    'meta_app_mode': 'development',
    'meta_app_review_status': 'not_started',
    'meta_business_verification': 'not_started',
    # LinkedIn
    'linkedin_client_id': '',
    'linkedin_version': '',
    'linkedin_scopes': 'openid,profile,email,w_member_social',
    'linkedin_member_posting': 'unknown',
    'linkedin_org_posting': 'unknown',
    # Ads
    'ads_enabled': '0',
    'ads_budget_increase_confirm_pct': '20',
}
SECRET_KEYS = {'meta_app_secret', 'linkedin_client_secret'}

META_PERMISSIONS = [
    ('pages_show_list', 'List the Facebook Pages you manage (needed to choose a Page).'),
    ('pages_read_engagement', 'Read Page content, followers and engagement on posts.'),
    ('pages_manage_posts', 'Create, edit and delete posts on the Page.'),
    ('read_insights', 'Read Page and post insights (reach, impressions).'),
    ('business_management', 'Access Pages and ad accounts owned through Business Manager.'),
    ('instagram_basic', 'Read the Instagram professional account profile and media.'),
    ('instagram_content_publish', 'Publish photos, videos, Reels and carousels to Instagram.'),
    ('instagram_manage_insights', 'Read Instagram account and media insights.'),
    ('ads_read', 'Read ad accounts, campaigns and ads reports (Facebook Ads section).'),
    ('ads_management', 'Create and manage campaigns (Facebook Ads section).'),
]
LINKEDIN_SCOPES = [
    ('openid', 'Sign in with LinkedIn (OpenID Connect) - identifies the member.'),
    ('profile', 'Member name and profile picture.'),
    ('email', 'Member email address (optional).'),
    ('w_member_social', 'Post on behalf of the member ("Share on LinkedIn" product).'),
    ('w_organization_social', 'Post on behalf of a company page (Community Management API, approval required).'),
    ('r_organization_social', 'Read company page posts and statistics (Community Management API).'),
    ('rw_organization_admin', 'List the company pages the member administers (Community Management API).'),
]


def get(key, default=None):
    row = db.session.get(SocialSetting, key)
    if row is None or row.value is None:
        if key == 'linkedin_version':
            return default if default is not None else _linkedin_default_version()
        return default if default is not None else DEFAULTS.get(key, '')
    if key == 'linkedin_version' and not row.value:
        return _linkedin_default_version()
    return row.value


def get_int(key, default=0):
    try:
        return int(get(key) or default)
    except (TypeError, ValueError):
        return default


def get_bool(key):
    return get(key) in ('1', 'true', 'True', 'on')


def set_value(key, value, user_id=None):
    row = db.session.get(SocialSetting, key)
    if row is None:
        row = SocialSetting(key=key)
        db.session.add(row)
    row.value = None if value is None else str(value)
    row.is_secret = False
    row.updated_by = user_id


def get_secret(key):
    row = db.session.get(SocialSetting, key)
    if row is None or not row.value:
        return ''
    return security.decrypt(row.value)


def has_secret(key):
    row = db.session.get(SocialSetting, key)
    return bool(row and row.value)


def set_secret(key, value, user_id=None):
    """Raises security.EncryptionNotConfigured when there is no key."""
    row = db.session.get(SocialSetting, key)
    if row is None:
        row = SocialSetting(key=key)
        db.session.add(row)
    row.value = security.encrypt(value) if value else None
    row.is_secret = True
    row.updated_by = user_id


def state_get(key):
    return get('state.' + key, '')


def state_set(key, value):
    set_value("state." + key, value)


def is_enabled():
    return get_bool('enabled')


# ── time ──────────────────────────────────────────────────────────────
def tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(get('timezone') or 'UTC')
    except Exception:
        return timezone.utc


def to_local(dt):
    if not dt:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(tz())


def local_to_utc(local_naive):
    """A naive datetime typed by the user in the module timezone -> naive UTC."""
    if not local_naive:
        return None
    return local_naive.replace(tzinfo=tz()).astimezone(timezone.utc).replace(tzinfo=None)


def local_now():
    return datetime.now(tz())


# ── persistence ───────────────────────────────────────────────────────
def commit_with_retry(attempts=4):
    """Commit, retrying briefly if SQLite reports the database is locked
    (the background publisher and web requests share the file)."""
    for i in range(attempts):
        try:
            db.session.commit()
            return
        except OperationalError as e:
            if 'locked' not in str(e).lower() or i == attempts - 1:
                db.session.rollback()
                raise
            time.sleep(0.2 * (2 ** i))


def audit(action, target=None, detail=None, success=True, user_id=None, commit=False):
    from flask_login import current_user
    if user_id is None and has_request_context() and getattr(current_user, 'is_authenticated', False):
        user_id = current_user.id
    db.session.add(SocialAuditLog(
        user_id=user_id, action=action[:60], target=(target or '')[:200] or None,
        detail=security.redact(detail or '')[:1000] or None, success=success,
        ip=(request.remote_addr if has_request_context() else None)))
    if commit:
        commit_with_retry()


def notify(kind, message, level='info', link=None, email=False):
    """In-module notification (Overview + header bell). Failures can also be
    emailed through the CRM's existing SMTP settings when enabled."""
    db.session.add(SocialNotification(kind=kind[:40], level=level, message=security.redact(message)[:500],
                                      link=(link or '')[:300] or None))
    if email and get_bool('notify_email_failures') and get('notify_email_to'):
        try:
            from app.system_mail.mailer import send_email
            for to in [a.strip() for a in get('notify_email_to').split(',') if a.strip()]:
                send_email(to, f'[CRM Social Media] {kind.replace("_", " ").title()}', security.redact(message))
        except Exception:
            pass  # email is best-effort; the in-app notification is recorded either way


# ── URLs ──────────────────────────────────────────────────────────────
def public_base_url():
    """Configured public HTTPS base URL (Settings > Media Storage), else the
    SOCIAL_MEDIA_PUBLIC_BASE_URL env var, else the current request's host."""
    base = (get('public_base_url') or os.environ.get('SOCIAL_MEDIA_PUBLIC_BASE_URL', '')).strip().rstrip('/')
    if base:
        return base
    if has_request_context():
        return request.host_url.rstrip('/')
    return ''


def external_url(endpoint, **values):
    """Absolute URL built on public_base_url(); '' when unknown (background job without a configured base)."""
    from flask import current_app, url_for
    base = public_base_url()
    if not base:
        return ''
    with current_app.test_request_context(base_url=base):
        return url_for(endpoint, _external=True, **values)


def redirect_uri(provider):
    return external_url('social_media.oauth_callback', provider=provider)


def mark_ready_problems():
    """List of blocking configuration problems for the Overview banner."""
    problems = []
    if not security.is_ready():
        problems.append(security.encryption_status()[1])
    return problems
