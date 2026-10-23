"""Jinja filters for the WhatsApp templates (times shown in the CRM's timezone)."""
from datetime import datetime, timezone

from app.whatsapp.services.stats import CRM_TZ


def _local(dt):
    if not dt:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(CRM_TZ) if CRM_TZ else dt


def wa_dt(dt, fmt='%d %b %Y, %I:%M %p'):
    d = _local(dt)
    return d.strftime(fmt) if d else '—'


def wa_ago(dt):
    if not dt:
        return '—'
    secs = (datetime.utcnow() - dt).total_seconds()
    if secs < 60:
        return 'just now'
    if secs < 3600:
        return f'{int(secs // 60)} min ago'
    if secs < 86400:
        return f'{int(secs // 3600)} h ago'
    if secs < 86400 * 7:
        return f'{int(secs // 86400)} d ago'
    return wa_dt(dt, '%d %b %Y')


def wa_pct(v):
    return '—' if v is None else f'{v:g}%'


def wa_iso(dt):
    return dt.isoformat() + 'Z' if dt else ''


def register(app):
    app.jinja_env.filters['wa_dt'] = wa_dt
    app.jinja_env.filters['wa_ago'] = wa_ago
    app.jinja_env.filters['wa_pct'] = wa_pct
    app.jinja_env.filters['wa_iso'] = wa_iso
