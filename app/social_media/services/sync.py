"""Analytics and history synchronisation.

* insights: metrics for destinations published in the last N days.
* posts:    existing platform posts the API lets us read, stored as
            SocialPost(origin='synced') with one published destination.
            Only what the API returns (latest posts, paginated up to a cap) -
            never presented as the complete history.
"""
from datetime import datetime, timedelta, timezone

from dateutil import parser as dtparser

from app import db
from app.social_media.models import SocialAccount, SocialAccountSync, SocialPost, SocialPostDestination
from app.social_media.services import accounts as acc_svc
from app.social_media.services import core, linkedin, meta, publisher
from app.social_media.services.http import ApiError

SYNC_POST_LIMIT = 100


def _utc(value):
    try:
        dt = dtparser.parse(value)
        return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
    except (TypeError, ValueError, OverflowError):
        return None


def metrics_for(dest, account, token):
    if dest.platform == 'facebook':
        return meta.facebook_post_metrics(dest.remote_id, token)
    if dest.platform == 'instagram':
        return meta.instagram_media_metrics(dest.remote_id, token)
    if dest.platform == 'linkedin' and account.account_type == 'organization':
        return linkedin.organization_post_stats(account.remote_id, dest.remote_id, token)
    return {}  # LinkedIn member post analytics are not available to standard apps


def sync_insights(account, days=60):
    log = SocialAccountSync(account_id=account.id, kind='insights', status='success')
    db.session.add(log)
    n, errors = 0, []
    try:
        token = acc_svc.token_for(account)
        since = datetime.utcnow() - timedelta(days=days)
        dests = SocialPostDestination.query.filter(
            SocialPostDestination.account_id == account.id, SocialPostDestination.status == 'published',
            SocialPostDestination.remote_id.isnot(None), SocialPostDestination.published_at >= since).all()
        for d in dests:
            try:
                publisher.store_metrics(d, metrics_for(d, account, token))
                n += 1
            except ApiError as e:
                errors.append(e.message)
                if e.kind in ('invalid_token', 'rate_limited'):
                    raise
        log.status = 'partial' if errors else 'success'
        log.message = (f'{n} posts updated.' + (f' {len(errors)} errors, e.g. {errors[0]}' if errors else ''))[:500]
    except ApiError as e:
        acc_svc.mark_auth_problem(account, e)
        log.status, log.message = 'error', e.message[:500]
    log.items, log.finished_at = n, datetime.utcnow()
    account.last_sync_at = datetime.utcnow()
    return log


def _store_remote(account, remote_id, text, created, url):
    """Create the synced post unless this remote id is already known (also
    covers posts the CRM itself published)."""
    if SocialPostDestination.query.filter_by(account_id=account.id, remote_id=str(remote_id)).first():
        return False
    post = SocialPost(title=None, body=text or '', status='published', origin='synced', published_at=created)
    db.session.add(post)
    db.session.flush()
    db.session.add(SocialPostDestination(post_id=post.id, account_id=account.id, platform=account.platform,
                                         status='published', remote_id=str(remote_id), remote_url=url,
                                         published_at=created))
    return True


def sync_posts(account):
    log = SocialAccountSync(account_id=account.id, kind='posts', status='success')
    db.session.add(log)
    n = 0
    try:
        token = acc_svc.token_for(account)
        if account.platform == 'facebook':
            for p in meta.facebook_recent_posts(account.remote_id, token, SYNC_POST_LIMIT):
                n += _store_remote(account, p['id'], p.get('message'), _utc(p.get('created_time')),
                                   p.get('permalink_url'))
        elif account.platform == 'instagram':
            for p in meta.instagram_recent_media(account.remote_id, token, SYNC_POST_LIMIT):
                n += _store_remote(account, p['id'], p.get('caption'), _utc(p.get('timestamp')), p.get('permalink'))
        else:
            for p in linkedin.recent_posts(account.remote_id, token, SYNC_POST_LIMIT):
                created = p.get('publishedAt') or p.get('createdAt')
                n += _store_remote(account, p['id'], p.get('commentary'),
                                   datetime.utcfromtimestamp(created / 1000) if created else None,
                                   f'https://www.linkedin.com/feed/update/{p["id"]}/')
        log.message = f'{n} new posts imported (latest {SYNC_POST_LIMIT} checked).'
    except ApiError as e:
        acc_svc.mark_auth_problem(account, e)
        log.status = 'error'
        log.message = e.message[:500]
        if account.platform == 'linkedin' and e.kind in ('missing_permission', 'app_review'):
            log.message = ('LinkedIn did not allow reading posts for this account (needs r_organization_social for '
                           'company pages; member post history is not available to standard apps).')[:500]
    log.items, log.finished_at = n, datetime.utcnow()
    account.last_sync_at = datetime.utcnow()
    return log


def sync_all(kind='insights'):
    for account in SocialAccount.query.filter_by(status='connected').all():
        (sync_insights if kind == 'insights' else sync_posts)(account)
        core.commit_with_retry()
