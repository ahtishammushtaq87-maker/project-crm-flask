"""Background publisher (APScheduler, already used by the CRM).

Runs every minute in the web process, like the CRM's other jobs: it is
skipped in Flask's reloader parent process and can be turned off with
SOCIAL_MEDIA_SCHEDULER_DISABLED=1, e.g. to run it in a single process only:

    flask --app run social-media-tick        (from cron, once a minute)

Running it in several processes at once is safe - destinations are claimed
atomically (see publisher.py) - it only wastes a few queries.

Job state lives in the database (social_post_destinations), so scheduled
posts survive restarts; nothing depends on a browser or a request.
"""
import os
import time
from datetime import datetime, timedelta

_scheduler = None


def tick(app, budget_seconds=50):
    """One scheduler pass. Returns a dict summary (also stored as health)."""
    with app.app_context():
        from app import db
        from app.social_media.services import accounts, core, publisher, sync
        started = time.monotonic()
        summary = {'published': 0, 'failed': 0, 'released': 0, 'error': None}
        try:
            summary['released'] = publisher.release_stale_locks()
            core.commit_with_retry()
            if core.is_enabled():
                for dest_id in publisher.due_destination_ids():
                    if time.monotonic() - started > budget_seconds:
                        break
                    d = publisher.publish_destination(dest_id, triggered_by='scheduler', wait_seconds=20)
                    if d is not None:
                        summary['published' if d.status == 'published' else 'failed'] += 1
            now = datetime.utcnow()
            if core.state_get('token_check_at') < (now - timedelta(hours=12)).isoformat():
                accounts.check_token_expiry()
                core.state_set('token_check_at', now.isoformat())
                core.commit_with_retry()
            if core.state_get('insights_at') < (now - timedelta(hours=6)).isoformat():
                core.state_set('insights_at', now.isoformat())
                core.commit_with_retry()
                sync.sync_all('insights')
            cleanup_media()
        except Exception as e:
            db.session.rollback()
            summary['error'] = f'{e.__class__.__name__}: {e}'[:300]
            app.logger.exception('Social Media scheduler tick failed')
        try:
            core.state_set('scheduler_last_tick', datetime.utcnow().isoformat())
            core.state_set('scheduler_last_status', 'error' if summary['error'] else 'ok')
            core.state_set('scheduler_last_error', summary['error'] or '')
            core.commit_with_retry()
        except Exception:
            db.session.rollback()
        db.session.remove()
        return summary


def cleanup_media():
    """Delete stored media files of drafts/cancelled posts older than N days
    (0 = keep forever). Records and published posts are never removed."""
    from app import db
    from app.social_media.models import SocialPost, SocialPostMedia
    from app.social_media.services import core, media
    days = core.get_int('media_cleanup_days', 0)
    now = datetime.utcnow()
    if days <= 0 or core.state_get('media_cleanup_at') > (now - timedelta(hours=24)).isoformat():
        return
    cut = now - timedelta(days=days)
    rows = SocialPostMedia.query.join(SocialPost).filter(SocialPost.status == 'cancelled',
                                                         SocialPost.updated_at < cut).all()
    for m in rows:
        media.delete_file(m)
        db.session.delete(m)
    core.state_set('media_cleanup_at', now.isoformat())
    core.commit_with_retry()


def health():
    """(status, last_tick_iso, error, next_due) for the Settings page."""
    from app.social_media.models import SocialPostDestination
    from app.social_media.services import core
    last = core.state_get('scheduler_last_tick')
    status = core.state_get('scheduler_last_status') or 'never_run'
    if last:
        try:
            if datetime.fromisoformat(last) < datetime.utcnow() - timedelta(minutes=5):
                status = 'stale'
        except ValueError:
            pass
    nxt = SocialPostDestination.query.filter(SocialPostDestination.status == 'scheduled').order_by(
        SocialPostDestination.scheduled_at).first()
    return {'status': status, 'last_tick': datetime.fromisoformat(last) if last else None,
            'error': core.state_get('scheduler_last_error'), 'next': nxt,
            'in_process': _scheduler is not None,
            'disabled_env': os.environ.get('SOCIAL_MEDIA_SCHEDULER_DISABLED') == '1'}


def start_scheduler(app):
    global _scheduler

    @app.cli.command('social-media-tick')
    def _tick_command():
        """Publish due social media posts once (for cron)."""
        print(tick(app))

    if os.environ.get('SOCIAL_MEDIA_SCHEDULER_DISABLED') == '1' or app.config.get('TESTING'):
        return
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return
    if _scheduler is not None:
        return
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(tick, 'interval', args=[app], seconds=60, id='social_media_publisher', max_instances=1,
                      coalesce=True, replace_existing=True,
                      next_run_time=datetime.now() + timedelta(seconds=45))  # let the app finish starting
    scheduler.start()
    _scheduler = scheduler
