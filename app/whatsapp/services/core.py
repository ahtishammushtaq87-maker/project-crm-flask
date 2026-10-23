"""Shared helpers: settings row, API client, audit log, error log, and
SQLite-lock-tolerant commits."""
import time
from datetime import datetime

from flask import has_request_context, request
from sqlalchemy.exc import OperationalError

from app import db
from app.whatsapp.models import WhatsAppApiError, WhatsAppAuditLog, WhatsAppSettings, WhatsAppState
from app.whatsapp.services.cloud_api import CloudAPI, Credentials


def get_settings(create=False):
    s = WhatsAppSettings.query.order_by(WhatsAppSettings.id).first()
    if s is None and create:
        s = WhatsAppSettings()
        db.session.add(s)
        db.session.flush()
    return s


def api(settings=None):
    """CloudAPI for the saved credentials. Raises cloud_api.ApiError(kind='not_configured')."""
    return CloudAPI(Credentials.from_settings(settings or get_settings()))


def commit_with_retry(attempts=4):
    """Commit, retrying briefly if SQLite reports the database is locked
    (concurrent webhook deliveries / background jobs)."""
    for i in range(attempts):
        try:
            db.session.commit()
            return
        except OperationalError as e:
            if 'locked' not in str(e).lower() or i == attempts - 1:
                db.session.rollback()
                raise
            time.sleep(0.2 * (2 ** i))


def audit(action, target=None, detail=None, user_id=None, commit=False):
    from flask_login import current_user
    if user_id is None and has_request_context() and getattr(current_user, 'is_authenticated', False):
        user_id = current_user.id
    db.session.add(WhatsAppAuditLog(
        user_id=user_id, action=action[:60], target=(target or '')[:120] or None,
        detail=(detail or '')[:500] or None,
        ip=(request.remote_addr if has_request_context() else None)))
    if commit:
        commit_with_retry()


def record_error(source, err=None, message=None, commit=False):
    db.session.add(WhatsAppApiError(
        source=source[:20],
        code=str(getattr(err, 'code', '') or '')[:20] or None,
        kind=getattr(err, 'kind', None),
        message=(message or getattr(err, 'message', None) or str(err or ''))[:500]))
    if commit:
        commit_with_retry()


def external_url(endpoint, **values):
    """Absolute URL, also from background jobs (no request): those use
    WHATSAPP_PUBLIC_BASE_URL, e.g. https://crm.example.com. Returns '' if unknown."""
    import os
    from flask import current_app, url_for
    if has_request_context():
        base = os.environ.get('WHATSAPP_PUBLIC_BASE_URL', '').rstrip('/')
        if base:
            return base + url_for(endpoint, **values)
        return url_for(endpoint, _external=True, **values)
    base = os.environ.get('WHATSAPP_PUBLIC_BASE_URL', '').rstrip('/')
    if not base:
        return ''
    with current_app.test_request_context(base_url=base):
        return url_for(endpoint, _external=True, **values)


def state_get(key, default=None):
    row = db.session.get(WhatsAppState, key)
    return row.value if row else default


def state_set(key, value):
    row = db.session.get(WhatsAppState, key)
    if row is None:
        row = WhatsAppState(key=key)
        db.session.add(row)
    row.value = str(value)
    row.updated_at = datetime.utcnow()
