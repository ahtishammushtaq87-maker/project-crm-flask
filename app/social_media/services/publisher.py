"""Publishing one destination, safely.

Duplicate protection:
  1. A destination is claimed with one atomic UPDATE (status scheduled /
     retry_wait -> publishing, with a fresh lock token). Only the worker whose
     UPDATE changed the row continues - concurrent schedulers, gunicorn
     workers or a user clicking twice cannot publish it twice.
  2. A destination that already has a remote_id is never published again.
  3. An attempt row ('started') is committed before calling the platform. If
     the process dies mid-call, the stale lock is turned into needs_review
     (outcome unknown) instead of being retried blindly.
  4. Errors where the request may have taken effect (timeouts after
     sending, 5xx on a write) are 'needs_review', never retried
     automatically. Rate limits and temporary outages retry with exponential
     backoff; permission/validation errors fail immediately.
  5. Instagram container ids are committed before media_publish, so a retry
     reuses the container rather than creating a second post.
"""
import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy import update

from app import db
from app.social_media.models import (SocialAccount, SocialPost, SocialPostDestination, SocialPostInsight,
                                     SocialPublishAttempt)
from app.social_media.services import accounts as acc_svc
from app.social_media.services import core, linkedin, meta
from app.social_media.services import media as media_svc
from app.social_media.services.http import ApiError

CLAIMABLE = ('scheduled', 'retry_wait')
STALE_LOCK = timedelta(minutes=20)
MAX_PROCESSING_WAITS = 40      # Instagram/LinkedIn media processing checks (~1/minute)


def claim(dest_id, now=None):
    """Atomically move a due destination to 'publishing'. Returns the lock token or None."""
    now = now or datetime.utcnow()
    token = uuid.uuid4().hex
    res = db.session.execute(
        update(SocialPostDestination)
        .where(SocialPostDestination.id == dest_id,
               SocialPostDestination.status.in_(CLAIMABLE),
               SocialPostDestination.remote_id.is_(None))
        .values(status='publishing', lock_token=token, locked_at=now)
        .execution_options(synchronize_session=False))
    core.commit_with_retry()
    return token if res.rowcount == 1 else None


def _backoff(failures):
    base = max(30, core.get_int('retry_base_seconds', 120))
    return timedelta(seconds=min(base * (2 ** max(0, failures - 1)), 6 * 3600) * random.uniform(0.85, 1.15))


def _text_for(dest):
    return dest.post.full_text(dest.custom_text)


def _do_publish(dest, account, wait_seconds):
    post = dest.post
    text = _text_for(dest)
    media_list = list(post.media)
    problems = media_svc.validate_for_platform(dest.platform, post, media_list, text)
    if problems:
        raise ApiError(' '.join(problems), kind='validation')
    token = acc_svc.token_for(account)
    if dest.platform == 'facebook':
        blobs = [(m, media_svc.read_bytes(m)) for m in media_list]
        return meta.publish_facebook(account.remote_id, token, text, post.link_url, blobs)
    if dest.platform == 'instagram':
        urls = []
        for m in media_list:
            m.public_enabled = True
            url = media_svc.public_url(m)
            if not url.startswith('https://'):
                raise ApiError('Instagram downloads media from a public HTTPS URL. Set the Public base URL in '
                               'API Settings > Media Storage.', kind='not_configured')
            urls.append((m.kind, url))
        core.commit_with_retry()

        def save_container(cid):
            dest.remote_container_id = cid
            core.commit_with_retry()
        return meta.publish_instagram(account.remote_id, token, text, urls, container_id=dest.remote_container_id,
                                      save_container=save_container, wait_seconds=wait_seconds)
    if dest.platform == 'linkedin':
        blobs = [(m, media_svc.read_bytes(m)) for m in media_list]
        return linkedin.publish(account.remote_id, token, text, post.link_url, blobs, link_title=post.title,
                                wait_seconds=wait_seconds)
    raise ApiError(f'Unsupported platform {dest.platform}.', kind='validation')


def publish_destination(dest_id, triggered_by='scheduler', user_id=None, wait_seconds=60):
    """Claim and publish one destination. Returns the destination (or None if
    another worker owns it / it is not due)."""
    lock = claim(dest_id)
    if not lock:
        return None
    dest = db.session.get(SocialPostDestination, dest_id)
    db.session.refresh(dest)
    account = db.session.get(SocialAccount, dest.account_id) if dest.account_id else None
    attempt = SocialPublishAttempt(destination_id=dest.id, triggered_by=triggered_by, user_id=user_id)
    db.session.add(attempt)
    core.commit_with_retry()

    now = datetime.utcnow()
    try:
        if account is None or account.status == 'disconnected':
            raise ApiError('The destination account is no longer connected.', kind='invalid_token')
        if not core.is_enabled():
            raise ApiError('Social media publishing is disabled in API Settings > General.', kind='not_configured',
                           retryable=True)
        remote_id, url = _do_publish(dest, account, wait_seconds)
        dest.status = 'published'
        dest.remote_id = str(remote_id)
        dest.remote_url = url or None
        dest.published_at = datetime.utcnow()
        dest.error_code = dest.error_kind = dest.error_message = None
        dest.next_attempt_at = None
        attempt.outcome, attempt.remote_id = 'success', str(remote_id)
        account.last_error = None
        core.audit('post_published', dest.post.display_title, f'{account.label} -> {remote_id}', user_id=user_id)
        if core.get_bool('notify_success'):
            core.notify('post_published', f'"{dest.post.display_title}" published to {account.label}.',
                        level='success', link=f'/social-media/posts/{dest.post_id}')
    except ApiError as e:
        _record_failure(dest, account, attempt, e, now, user_id)
    except Exception as e:  # never let one destination crash the worker
        db.session.rollback()
        dest = db.session.get(SocialPostDestination, dest_id)
        attempt = SocialPublishAttempt.query.filter_by(destination_id=dest_id).order_by(
            SocialPublishAttempt.id.desc()).first()
        _record_failure(dest, account, attempt, ApiError(f'Internal error: {e.__class__.__name__}', kind='ambiguous',
                                                         ambiguous=True), now, user_id)
    dest.lock_token = None
    dest.locked_at = None
    attempt.finished_at = datetime.utcnow()
    refresh_post_status(dest.post)
    core.commit_with_retry()
    return dest


def _record_failure(dest, account, attempt, err, now, user_id):
    attempt.error_code = str(err.code or err.kind)[:40]
    attempt.error_message = err.message[:500]
    attempt.http_status = err.http_status
    dest.error_code = str(err.code or '')[:40] or None
    dest.error_kind = err.kind
    dest.error_message = err.message[:500]
    max_retries = max(0, core.get_int('max_retries', 3))
    if err.kind == 'processing':
        waits = SocialPublishAttempt.query.filter_by(destination_id=dest.id, outcome='pending').count()
        if waits < MAX_PROCESSING_WAITS:
            dest.status, attempt.outcome = 'retry_wait', 'pending'
            dest.next_attempt_at = now + timedelta(seconds=60)
            return
        err = ApiError('Media processing did not finish in time.', kind='validation')
        dest.error_kind, dest.error_message = err.kind, err.message
    if err.ambiguous:
        dest.status, attempt.outcome = 'needs_review', 'unknown'
    elif err.retryable and dest.failure_count < max_retries:
        dest.failure_count += 1
        dest.status, attempt.outcome = 'retry_wait', 'retry'
        dest.next_attempt_at = now + _backoff(dest.failure_count)
        core.notify('publish_retry', f'"{dest.post.display_title}" on {account.label if account else "?"}: '
                    f'{err.message} Retrying at {core.to_local(dest.next_attempt_at):%H:%M}.', level='warning',
                    link=f'/social-media/posts/{dest.post_id}')
    else:
        dest.status, attempt.outcome = 'failed', 'failed'
        dest.failure_count += 1
    if account is not None:
        acc_svc.mark_auth_problem(account, err)
    if dest.status in ('failed', 'needs_review') and core.get_bool('notify_failure'):
        verb = 'needs review' if dest.status == 'needs_review' else 'failed'
        core.notify('publish_failed', f'"{dest.post.display_title}" {verb} on '
                    f'{account.label if account else "a removed account"}: {err.message}',
                    level='danger', link=f'/social-media/posts/{dest.post_id}', email=True)
    core.audit('post_publish_failed', dest.post.display_title,
               f'{account.label if account else "-"}: [{err.kind}] {err.message}', success=False, user_id=user_id)


def refresh_post_status(post):
    """Post status from its destinations. Partial success is never shown as
    success."""
    if post.origin == 'synced':
        return
    sts = [d.status for d in post.destinations]
    if not sts or all(s == 'draft' for s in sts):
        post.status = 'draft' if post.status not in ('cancelled',) else post.status
        return
    live = [s for s in sts if s != 'cancelled']
    published = sum(1 for s in live if s == 'published')
    in_flight = any(s in ('publishing', 'retry_wait') for s in live)
    waiting = any(s == 'scheduled' for s in live)
    bad = any(s in ('failed', 'needs_review') for s in live)
    if not live:
        post.status = 'cancelled'
    elif in_flight or (waiting and published):
        post.status = 'publishing'
    elif waiting and not bad:
        post.status = 'scheduled'
    elif published == len(live):
        post.status = 'published'
    elif published:
        post.status = 'partially_published'
    elif bad and not waiting:
        post.status = 'failed'
    else:
        post.status = 'publishing'
    if published:
        times = [d.published_at for d in post.destinations if d.published_at]
        post.published_at = min(times) if times else post.published_at


def release_stale_locks(now=None):
    """Destinations stuck in 'publishing' (worker died mid-call) -> needs_review."""
    now = now or datetime.utcnow()
    stale = SocialPostDestination.query.filter(SocialPostDestination.status == 'publishing',
                                               SocialPostDestination.locked_at < now - STALE_LOCK).all()
    for d in stale:
        d.status = 'needs_review'
        d.error_kind = 'ambiguous'
        d.error_message = ('Publishing was interrupted (worker stopped). Check the account on the platform; '
                           'if the post is not there, use Retry.')
        d.lock_token = d.locked_at = None
        for a in d.attempts:
            if a.outcome == 'started':
                a.outcome, a.finished_at = 'unknown', now
        refresh_post_status(d.post)
        core.notify('publish_failed', f'"{d.post.display_title}" needs review: publishing was interrupted.',
                    level='danger', link=f'/social-media/posts/{d.post_id}')
    return len(stale)


def due_destination_ids(now=None, limit=20):
    now = now or datetime.utcnow()
    q = SocialPostDestination.query.with_entities(SocialPostDestination.id).filter(
        SocialPostDestination.remote_id.is_(None),
        ((SocialPostDestination.status == 'scheduled') & (SocialPostDestination.scheduled_at <= now)) |
        ((SocialPostDestination.status == 'retry_wait') & (SocialPostDestination.next_attempt_at <= now)))
    return [r[0] for r in q.order_by(SocialPostDestination.scheduled_at).limit(limit).all()]


def manual_retry(dest, user_id):
    """User-confirmed retry of a failed / needs_review destination."""
    if dest.remote_id or dest.status not in ('failed', 'needs_review'):
        return False
    dest.status = 'scheduled'
    dest.scheduled_at = datetime.utcnow()
    dest.next_attempt_at = None
    dest.failure_count = 0
    dest.error_kind = dest.error_message = dest.error_code = None
    refresh_post_status(dest.post)
    core.audit('post_retry', dest.post.display_title, dest.account.label if dest.account else '', user_id=user_id)
    core.commit_with_retry()
    return True


def store_metrics(dest, metrics):
    if not metrics:
        return
    snap = SocialPostInsight(destination_id=dest.id, **{k: metrics.get(k) for k in (
        'impressions', 'reach', 'engagements', 'likes', 'comments', 'shares', 'saves', 'clicks', 'video_views')})
    db.session.add(snap)
    dest.impressions = metrics.get('impressions')
    dest.reach = metrics.get('reach')
    dest.engagements = metrics.get('engagements')
    dest.insights_synced_at = datetime.utcnow()


def post_for_update(post_id):
    return db.session.get(SocialPost, post_id)
