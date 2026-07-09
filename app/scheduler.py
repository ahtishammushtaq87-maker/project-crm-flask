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
