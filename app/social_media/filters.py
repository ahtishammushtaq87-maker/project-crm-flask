"""Jinja filters for the Social Media templates (times in the module timezone;
missing metrics shown as "Not available", never as 0)."""
from datetime import datetime
from decimal import Decimal


def sm_dt(dt, fmt='%d %b %Y, %I:%M %p'):
    from app.social_media.services import core
    local = core.to_local(dt)
    return local.strftime(fmt) if local else '—'


def sm_input_dt(dt):
    """Value for <input type=datetime-local> in the module timezone."""
    return sm_dt(dt, '%Y-%m-%dT%H:%M') if dt else ''


def sm_ago(dt):
    if not dt:
        return 'never'
    secs = (datetime.utcnow() - dt).total_seconds()
    future = secs < 0
    secs = abs(secs)
    for size, unit in ((86400, 'day'), (3600, 'hour'), (60, 'minute')):
        if secs >= size:
            n = int(secs // size)
            text = f'{n} {unit}{"s" if n != 1 else ""}'
            return f'in {text}' if future else f'{text} ago'
    return 'just now'


def sm_num(v, na='Not available'):
    if v is None:
        return na
    if isinstance(v, float) and not v.is_integer():
        return f'{v:,.2f}'
    return f'{int(v):,}'


def sm_pct(v, na='Not available'):
    return na if v is None else f'{float(v):.2f}%'


def sm_money(v, currency, na='Not available'):
    if v in (None, ''):
        return na
    try:
        return f'{Decimal(str(v)):,.2f} {currency or ""}'.strip()
    except Exception:
        return na


def register(app):
    for f in (sm_dt, sm_input_dt, sm_ago, sm_num, sm_pct, sm_money):
        app.jinja_env.filters[f.__name__] = f
