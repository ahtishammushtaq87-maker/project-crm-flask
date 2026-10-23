"""Dashboard and report figures, all computed from stored records.

Rates use only messages whose outcome Meta has reported; when the
denominator is zero the rate is None (shown as "—"), never 0 % or 100 %.
"""
from datetime import datetime, timedelta

from sqlalchemy import and_, case, func

from app import db
from app.whatsapp.models import (WhatsAppApiError, WhatsAppCampaign, WhatsAppCampaignRecipient, WhatsAppContact,
                                 WhatsAppConversation, WhatsAppMessage, WhatsAppTemplate)
from app.whatsapp.services.campaigns import counts as campaign_counts

try:
    from zoneinfo import ZoneInfo
    CRM_TZ = ZoneInfo('Asia/Karachi')
except Exception:  # pragma: no cover
    CRM_TZ = None


def date_range(preset, start=None, end=None):
    """(from_utc, to_utc, label) for today | 7d | 30d | custom, using CRM local days."""
    now_local = datetime.now(CRM_TZ) if CRM_TZ else datetime.utcnow()
    today = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    if preset == 'today':
        a, b, label = today, today + timedelta(days=1), 'Today'
    elif preset == 'custom' and start:
        try:
            a = datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=today.tzinfo)
            b = datetime.strptime(end or start, '%Y-%m-%d').replace(tzinfo=today.tzinfo) + timedelta(days=1)
        except ValueError:
            return date_range('7d')
        if b <= a or (b - a).days > 731:
            return date_range('7d')
        label = f'{a:%d %b %Y} – {(b - timedelta(days=1)):%d %b %Y}'
    elif preset == '30d':
        a, b, label = today - timedelta(days=29), today + timedelta(days=1), 'Last 30 days'
    else:
        a, b, label = today - timedelta(days=6), today + timedelta(days=1), 'Last 7 days'

    def to_utc(d):
        return d.astimezone(ZoneInfo('UTC')).replace(tzinfo=None) if CRM_TZ else d
    return to_utc(a), to_utc(b), label


def rate(part, whole):
    return round(100.0 * part / whole, 1) if whole else None


def message_stats(a, b, user_id=None):
    q = db.session.query(
        func.sum(case((WhatsAppMessage.direction == 'in', 1), else_=0)),
        func.sum(case((WhatsAppMessage.direction == 'out', 1), else_=0)),
        func.sum(case((and_(WhatsAppMessage.direction == 'out', WhatsAppMessage.status == 'failed'), 1), else_=0)),
        func.sum(case((and_(WhatsAppMessage.direction == 'out',
                            WhatsAppMessage.status.in_(('delivered', 'read'))), 1), else_=0)),
        func.sum(case((and_(WhatsAppMessage.direction == 'out', WhatsAppMessage.status == 'read'), 1), else_=0)),
        func.sum(case((and_(WhatsAppMessage.direction == 'out',
                            WhatsAppMessage.status.in_(('sent', 'delivered', 'read', 'failed'))), 1), else_=0)),
    ).filter(WhatsAppMessage.timestamp >= a, WhatsAppMessage.timestamp < b)
    if user_id:
        q = q.filter(WhatsAppMessage.sent_by_id == user_id)
    inbound, outbound, failed, delivered, read, resolved = [int(x or 0) for x in q.one()]
    return {
        'inbound': inbound, 'outbound': outbound, 'failed': failed, 'delivered': delivered, 'read': read,
        'with_outcome': resolved,
        'pending_outcome': max(0, outbound - resolved),
        'delivery_rate': rate(delivered, resolved),
        'read_rate': rate(read, delivered),
        'failure_rate': rate(failed, resolved),
    }


def dashboard(a, b):
    conv = db.session.query(
        func.count(WhatsAppConversation.id),
        func.sum(case((WhatsAppConversation.status == 'open', 1), else_=0)),
        func.sum(case((WhatsAppConversation.unread_count > 0, 1), else_=0)),
    ).one()
    camp = dict(db.session.query(WhatsAppCampaign.status, func.count()).group_by(WhatsAppCampaign.status).all())
    return {
        'conversations': int(conv[0] or 0), 'open': int(conv[1] or 0), 'unread': int(conv[2] or 0),
        'subscribed': WhatsAppContact.query.filter_by(consent_status='opted_in').count(),
        'contacts': WhatsAppContact.query.count(),
        'campaigns_running': camp.get('running', 0) + camp.get('scheduled', 0),
        'campaigns_completed': camp.get('completed', 0),
        'messages': message_stats(a, b),
        'new_conversations': WhatsAppConversation.query.filter(WhatsAppConversation.created_at >= a,
                                                               WhatsAppConversation.created_at < b).count(),
    }


def daily_series(a, b):
    day = func.date(WhatsAppMessage.timestamp)
    rows = (db.session.query(day, func.sum(case((WhatsAppMessage.direction == 'in', 1), else_=0)),
                             func.sum(case((WhatsAppMessage.direction == 'out', 1), else_=0)))
            .filter(WhatsAppMessage.timestamp >= a, WhatsAppMessage.timestamp < b).group_by(day).all())
    data = {str(d): (int(i or 0), int(o or 0)) for d, i, o in rows}
    out, d = [], a.date()
    while d < b.date() or (d == b.date() and len(out) == 0):
        i, o = data.get(d.isoformat(), (0, 0))
        out.append({'date': d.isoformat(), 'in': i, 'out': o})
        d += timedelta(days=1)
        if len(out) > 400:
            break
    return out


def report(a, b, user_id=None, campaign_id=None, status=None):
    from app.models import User
    msgs = message_stats(a, b, user_id)
    by_status = dict(db.session.query(WhatsAppConversation.status, func.count())
                     .group_by(WhatsAppConversation.status).all())
    workload = (db.session.query(User.id, User.username,
                                 func.count(WhatsAppConversation.id),
                                 func.sum(case((WhatsAppConversation.status != 'resolved', 1), else_=0)))
                .join(WhatsAppConversation, WhatsAppConversation.assigned_to_id == User.id)
                .group_by(User.id, User.username).order_by(func.count(WhatsAppConversation.id).desc()).all())
    sent_by = dict(db.session.query(WhatsAppMessage.sent_by_id, func.count())
                   .filter(WhatsAppMessage.direction == 'out', WhatsAppMessage.timestamp >= a,
                           WhatsAppMessage.timestamp < b, WhatsAppMessage.sent_by_id.isnot(None))
                   .group_by(WhatsAppMessage.sent_by_id).all())
    # First response time: conversations whose first staff reply happened in the range.
    resp_rows = (db.session.query(WhatsAppConversation.created_at, WhatsAppConversation.first_response_at)
                 .filter(WhatsAppConversation.first_response_at >= a, WhatsAppConversation.first_response_at < b)
                 .all())
    secs = sorted((r - c).total_seconds() for c, r in resp_rows if c and r and r >= c)
    median_response = secs[len(secs) // 2] if secs else None

    campaigns_q = WhatsAppCampaign.query.filter(WhatsAppCampaign.created_at < b)
    if campaign_id:
        campaigns_q = campaigns_q.filter(WhatsAppCampaign.id == campaign_id)
    campaigns = [(c, campaign_counts(c)) for c in campaigns_q.order_by(WhatsAppCampaign.created_at.desc()).limit(25)]

    tpl_rows = (db.session.query(WhatsAppMessage.template_name, func.count(),
                                 func.sum(case((WhatsAppMessage.status.in_(('delivered', 'read')), 1), else_=0)),
                                 func.sum(case((WhatsAppMessage.status == 'read', 1), else_=0)),
                                 func.sum(case((WhatsAppMessage.status == 'failed', 1), else_=0)))
                .filter(WhatsAppMessage.msg_type == 'template', WhatsAppMessage.timestamp >= a,
                        WhatsAppMessage.timestamp < b)
                .group_by(WhatsAppMessage.template_name).order_by(func.count().desc()).limit(25).all())
    templates = [{'name': n, 'sent': int(s or 0), 'delivered': int(d or 0), 'read': int(r or 0),
                  'failed': int(f or 0), 'delivery_rate': rate(int(d or 0), int(d or 0) + int(f or 0))}
                 for n, s, d, r, f in tpl_rows]

    growth = WhatsAppContact.query.filter(WhatsAppContact.created_at >= a, WhatsAppContact.created_at < b).count()
    opt_outs = WhatsAppContact.query.filter(WhatsAppContact.opted_out_at >= a,
                                            WhatsAppContact.opted_out_at < b).count()
    opt_ins = WhatsAppContact.query.filter(WhatsAppContact.consent_at >= a, WhatsAppContact.consent_at < b).count()
    errors = (db.session.query(WhatsAppApiError.source, WhatsAppApiError.kind, func.count())
              .filter(WhatsAppApiError.created_at >= a, WhatsAppApiError.created_at < b)
              .group_by(WhatsAppApiError.source, WhatsAppApiError.kind).order_by(func.count().desc()).all())
    failed_q = (WhatsAppMessage.query.filter(WhatsAppMessage.direction == 'out',
                                             WhatsAppMessage.timestamp >= a, WhatsAppMessage.timestamp < b))
    if status:
        failed_q = failed_q.filter(WhatsAppMessage.status == status)
    return {
        'messages': msgs, 'by_status': by_status, 'workload': workload, 'sent_by': sent_by,
        'median_response': median_response, 'responses': len(secs), 'campaigns': campaigns,
        'templates': templates, 'growth': growth, 'opt_outs': opt_outs, 'opt_ins': opt_ins, 'errors': errors,
        'status_filter_count': failed_q.count() if status else None,
        'template_count': WhatsAppTemplate.query.filter_by(status='APPROVED').count(),
        'recipients_total': WhatsAppCampaignRecipient.query.count(),
    }
