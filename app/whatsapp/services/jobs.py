"""Optional background job (APScheduler, already used by the CRM): campaign
sending, the CRM-event scan for automations, and retention cleanup.

Runs once a minute in the web process. Like the CRM's other jobs it is
skipped in Flask's reloader parent process, and can be turned off with
WHATSAPP_SCHEDULER_DISABLED=1 (e.g. with several gunicorn workers, run it
in only one by disabling it elsewhere, or call ``run_once`` from cron:
    flask --app run whatsapp-tick).
Without the job, the inbox and webhooks work normally; only scheduled
campaigns, invoice automations and cleanup wait.
"""
import os
import time
from datetime import datetime, timedelta

_scheduler = None


def run_once(app):
    with app.app_context():
        from app import db
        from app.whatsapp.services import automations, campaigns
        for name, fn in (('campaigns', campaigns.tick), ('automations', automations.scan_crm_events),
                         ('cleanup', cleanup)):
            try:
                fn()
            except Exception:
                db.session.rollback()
                app.logger.exception('WhatsApp background job "%s" failed', name)
        db.session.remove()


def cleanup():
    """Retention: cached media files and old webhook/error/automation logs."""
    from app import db
    from app.whatsapp import media_root
    from app.whatsapp.models import (WhatsAppApiError, WhatsAppAutomationLog, WhatsAppMessage,
                                     WhatsAppWebhookEvent)
    from app.whatsapp.services import core
    s = core.get_settings()
    if s is None:
        return
    now = datetime.utcnow()
    if core.state_get('cleanup_at') and core.state_get('cleanup_at') > (now - timedelta(hours=6)).isoformat():
        return
    media_cut = time.time() - max(1, s.media_retention_days or 7) * 86400
    root = media_root()
    removed = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            p = os.path.join(dirpath, f)
            try:
                if os.path.getmtime(p) < media_cut:
                    os.remove(p)
                    removed.append(os.path.relpath(p, root))
            except OSError:
                pass
    if removed:
        WhatsAppMessage.query.filter(WhatsAppMessage.media_local_path.in_(removed)).update(
            {'media_local_path': None}, synchronize_session=False)
    log_cut = now - timedelta(days=max(7, s.log_retention_days or 30))
    for model, col in ((WhatsAppWebhookEvent, WhatsAppWebhookEvent.received_at),
                       (WhatsAppApiError, WhatsAppApiError.created_at)):
        model.query.filter(col < log_cut).delete(synchronize_session=False)
    # Automation logs are dedupe keys too: keep them 4x longer than other logs.
    WhatsAppAutomationLog.query.filter(WhatsAppAutomationLog.created_at < now - timedelta(
        days=4 * max(7, s.log_retention_days or 30))).delete(synchronize_session=False)
    core.state_set('cleanup_at', now.isoformat())
    db.session.commit()


def start_scheduler(app):
    global _scheduler

    @app.cli.command('whatsapp-tick')
    def _tick_command():
        """Run the WhatsApp campaign/automation/cleanup job once."""
        run_once(app)

    if os.environ.get('WHATSAPP_SCHEDULER_DISABLED') == '1' or app.config.get('TESTING'):
        return
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return
    if _scheduler is not None:
        return
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(run_once, 'interval', args=[app], seconds=60, id='whatsapp_jobs', max_instances=1,
                      coalesce=True, replace_existing=True)
    scheduler.start()
    _scheduler = scheduler
