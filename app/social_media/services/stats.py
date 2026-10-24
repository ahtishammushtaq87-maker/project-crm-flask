"""Dashboard / analytics numbers, computed only from stored records. A
metric no destination reported stays None and is shown as "Not available"."""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func

from app.social_media.models import (SocialAccount, SocialAdCampaign, SocialPost, SocialPostDestination)
from app.social_media.services import core

PRESETS = [('today', 'Today'), ('7d', 'Last 7 days'), ('30d', 'Last 30 days'), ('month', 'This month'),
           ('prev_month', 'Previous month')]


def resolve_range(args):
    """(preset, start_date, end_date, label, start_utc, end_utc) in the module timezone."""
    today = core.local_now().date()
    preset = args.get('range') or '30d'
    start = end = today
    if preset == 'today':
        pass
    elif preset == '7d':
        start = today - timedelta(days=6)
    elif preset == 'month':
        start = today.replace(day=1)
    elif preset == 'prev_month':
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif preset == 'custom':
        try:
            start = date.fromisoformat(args.get('start'))
            end = date.fromisoformat(args.get('end'))
        except (TypeError, ValueError):
            preset, start = '30d', today - timedelta(days=29)
        if end < start:
            start, end = end, start
        end = min(end, start + timedelta(days=366))
    else:
        preset, start = '30d', today - timedelta(days=29)
    label = dict(PRESETS).get(preset) or f'{start:%d %b %Y} – {end:%d %b %Y}'
    s_utc = core.local_to_utc(datetime.combine(start, time.min))
    e_utc = core.local_to_utc(datetime.combine(end + timedelta(days=1), time.min))
    return preset, start, end, label, s_utc, e_utc


def _sum_or_none(values):
    vals = [v for v in values if v is not None]
    return sum(vals) if vals else None


def overview(s_utc, e_utc, account_ids=None):
    D = SocialPostDestination
    published = D.query.filter(D.status == 'published', D.published_at >= s_utc, D.published_at < e_utc)
    if account_ids is not None:
        published = published.filter(D.account_id.in_(account_ids))
    pub_rows = published.all()
    crm_rows = [d for d in pub_rows if d.post.origin == 'crm']
    reach = _sum_or_none(d.reach for d in pub_rows)
    engagements = _sum_or_none(d.engagements for d in pub_rows)
    month_start = core.local_to_utc(datetime.combine(core.local_now().date().replace(day=1), time.min))
    posts = SocialPost.query.filter(SocialPost.origin == 'crm')
    return {
        'accounts': SocialAccount.query.filter_by(status='connected').count(),
        'accounts_attention': SocialAccount.query.filter(SocialAccount.status.in_(['reauth_required', 'error'])).count(),
        'published_month': D.query.join(SocialPost).filter(SocialPost.origin == 'crm', D.status == 'published',
                                                           D.published_at >= month_start).count(),
        'published_range': len(crm_rows),
        'scheduled': posts.filter(SocialPost.status == 'scheduled').count(),
        'drafts': posts.filter(SocialPost.status == 'draft').count(),
        'failed': posts.filter(SocialPost.status.in_(['failed', 'partially_published'])).count(),
        'needs_review': D.query.filter(D.status.in_(['failed', 'needs_review'])).count(),
        'impressions': _sum_or_none(d.impressions for d in pub_rows),
        'reach': reach,
        'engagements': engagements,
        'engagement_rate': (engagements / reach * 100) if reach and engagements is not None else None,
        'active_campaigns': SocialAdCampaign.query.filter(SocialAdCampaign.effective_status == 'ACTIVE').count(),
    }


def daily_series(s_utc, e_utc, start, end):
    """Per-day published count and engagements (local dates)."""
    D = SocialPostDestination
    rows = D.query.filter(D.status == 'published', D.published_at >= s_utc, D.published_at < e_utc).all()
    days = {}
    d = start
    while d <= end:
        days[d] = {'date': d.strftime('%d %b'), 'published': 0, 'engagements': 0, 'has_eng': False}
        d += timedelta(days=1)
    for r in rows:
        key = core.to_local(r.published_at).date()
        if key in days:
            days[key]['published'] += 1
            if r.engagements is not None:
                days[key]['engagements'] += r.engagements
                days[key]['has_eng'] = True
    return list(days.values())


def by_platform(s_utc, e_utc):
    D = SocialPostDestination
    out = []
    for platform in ('facebook', 'instagram', 'linkedin'):
        rows = D.query.filter(D.platform == platform, D.status == 'published', D.published_at >= s_utc,
                              D.published_at < e_utc).all()
        reach = _sum_or_none(r.reach for r in rows)
        eng = _sum_or_none(r.engagements for r in rows)
        out.append({'platform': platform, 'posts': len(rows), 'impressions': _sum_or_none(r.impressions for r in rows),
                    'reach': reach, 'engagements': eng,
                    'rate': (eng / reach * 100) if reach and eng is not None else None})
    return out


def status_counts():
    rows = SocialPost.query.with_entities(SocialPost.status, func.count()).filter(
        SocialPost.origin == 'crm').group_by(SocialPost.status).all()
    return dict(rows)
