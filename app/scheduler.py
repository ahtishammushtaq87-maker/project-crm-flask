"""
In-process background scheduler.

Runs the Sales Recovery automation (app.services.recovery_automation.run_daily_automation)
on a timer so recovery tasks/reminders get created and, critically, closed out
promptly once an invoice is paid — instead of only whenever an admin happens to
click "Run Automation" on the dashboard.
"""
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

_scheduler = None


def start_recovery_scheduler(app):
    """Start the background job exactly once per running process.

    Guards against:
      - Flask's debug reloader, which forks a second process (only the child
        that owns the real server, marked by WERKZEUG_RUN_MAIN, starts the job).
      - RECOVERY_SCHEDULER_DISABLED=1, an escape hatch for deployments that run
        multiple gunicorn workers and instead trigger automation via an
        external cron hitting a dedicated endpoint, to avoid running the job
        redundantly in every worker.
    """
    global _scheduler

    if os.environ.get('RECOVERY_SCHEDULER_DISABLED') == '1':
        return

    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return  # this is the reloader's watcher process, not the real server

    if _scheduler is not None:
        return  # already started in this process

    interval_minutes = int(os.environ.get('RECOVERY_SCHEDULER_INTERVAL_MINUTES', '15'))

    def _run():
        with app.app_context():
            from app.services.recovery_automation import run_daily_automation
            try:
                run_daily_automation()
            except Exception:
                app.logger.exception('Recovery automation background run failed')

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _run,
        'interval',
        minutes=interval_minutes,
        id='recovery_automation',
        next_run_time=None,  # first run scheduled below, right after startup
        replace_existing=True,
    )
    scheduler.start()
    scheduler.modify_job('recovery_automation', next_run_time=datetime.now())
    _scheduler = scheduler


_backup_scheduler = None


def start_backup_scheduler(app):
    """Start the nightly automatic-database-backup job exactly once per
    running process, firing daily at 10:00 PM Pakistan time. Same guards as
    start_recovery_scheduler() above (separate scheduler instance/guard so
    this can never interfere with the recovery job)."""
    global _backup_scheduler

    if os.environ.get('BACKUP_SCHEDULER_DISABLED') == '1':
        return

    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return  # this is the reloader's watcher process, not the real server

    if _backup_scheduler is not None:
        return  # already started in this process

    def _run():
        with app.app_context():
            from app.routes.backup import create_backup
            try:
                create_backup(backup_type='auto')
            except Exception:
                app.logger.exception('Automatic nightly database backup failed')

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _run,
        'cron',
        hour=22, minute=0,
        timezone='Asia/Karachi',
        id='nightly_database_backup',
        replace_existing=True,
    )
    scheduler.start()
    _backup_scheduler = scheduler


_production_target_scheduler = None


def start_production_target_scheduler(app):
    """Start the Production Target Tracker auto-finalization job exactly once
    per running process. Checks for targets whose deadline has passed and
    freezes their result (moving them from the Active tab to the Previous
    Targets tab) — this is what actually makes a target "stop" the moment
    its countdown reaches zero, even if nobody has the page open. Same
    guards as start_recovery_scheduler() above (separate scheduler instance
    so this can never interfere with the other jobs)."""
    global _production_target_scheduler

    if os.environ.get('PRODUCTION_TARGET_SCHEDULER_DISABLED') == '1':
        return

    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return  # this is the reloader's watcher process, not the real server

    if _production_target_scheduler is not None:
        return  # already started in this process

    interval_minutes = int(os.environ.get('PRODUCTION_TARGET_SCHEDULER_INTERVAL_MINUTES', '1'))

    def _run():
        with app.app_context():
            from app.services.production_targets import finalize_overdue_targets
            try:
                finalize_overdue_targets()
            except Exception:
                app.logger.exception('Production target auto-finalization background run failed')

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _run,
        'interval',
        minutes=interval_minutes,
        id='production_target_finalization',
        next_run_time=None,
        replace_existing=True,
    )
    scheduler.start()
    scheduler.modify_job('production_target_finalization', next_run_time=datetime.now())
    _production_target_scheduler = scheduler
