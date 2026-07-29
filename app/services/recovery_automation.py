"""
Sales Recovery Automation Service
Runs daily to:
  - Create recovery tasks for newly-overdue invoices
  - Update risk levels and overdue counts
  - Handle missed promise dates
  - Close tasks when invoice is fully paid
"""

from datetime import date, datetime
from app import db
from app.models import Sale, RecoveryTask, RecoveryLog, Task
from app.utils import pk_now


def run_daily_automation():
    """Main entry point called by the daily job or manual trigger."""
    results = {
        'tasks_created': 0,
        'tasks_closed': 0,
        'promises_missed': 0,
        'risk_updated': 0,
        'reminders_created': 0,
        'errors': [],
    }

    today = date.today()

    # All invoices with an outstanding balance
    open_invoices = Sale.query.filter(
        Sale.status.in_(['unpaid', 'partial']),
        Sale.is_approved == True,
        Sale.is_rejected == False,
    ).all()

    for invoice in open_invoices:
        try:
            _process_invoice(invoice, today, results)
        except Exception as e:
            results['errors'].append(f'Invoice {invoice.invoice_number}: {e}')

    # Safety net: close any recovery task left open even though its invoice is
    # already fully paid. Sale.update_status() closes the task in real time on
    # every normal payment path, but this catches stragglers left behind by a
    # path that changed paid_amount/status without going through it (bulk
    # scripts, manual DB edits, older data) — otherwise nothing would ever
    # clear them, since the open_invoices query above only looks at
    # unpaid/partial invoices and never revisits paid ones.
    stuck_tasks = RecoveryTask.query.join(
        Sale, RecoveryTask.invoice_id == Sale.id
    ).filter(
        Sale.status == 'paid',
        RecoveryTask.recovery_status.notin_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF']),
    ).all()
    for task in stuck_tasks:
        task.recovery_status = 'CLOSED_PAID'
        task.closed_at = datetime.utcnow()
        _cancel_reminders(task)
        results['tasks_closed'] += 1

    # Flush so newly-created RecoveryTasks are visible to the query below.
    db.session.flush()

    # Check promises on all open tasks
    open_tasks = RecoveryTask.query.filter(
        RecoveryTask.recovery_status.notin_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF'])
    ).all()

    for task in open_tasks:
        try:
            _check_promise(task, today, results)
            _refresh_risk(task, results)
            # Every open recovery task should have a live reminder for its
            # linked salesman user (auto-created here, no-op if one exists).
            _ensure_reminder(task, results)
        except Exception as e:
            results['errors'].append(f'Task {task.id}: {e}')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        results['errors'].append(f'Commit error: {e}')

    return results


def _process_invoice(invoice, today, results):
    # Caller (open_invoices) only ever passes unpaid/partial invoices, so a
    # 'paid' status is never seen here — closing paid invoices' tasks is
    # handled by Sale.update_status()'s real-time hook and the stuck_tasks
    # reconciliation pass in run_daily_automation().
    existing_task = invoice.recovery_task

    # Overdue by the single due_date OR by an installment tranche that's past
    # its own date and still short-funded (see Sale.effective_is_overdue).
    if not invoice.effective_is_overdue:
        return  # not overdue yet — nothing to do

    if not existing_task:
        task = RecoveryTask(
            invoice_id=invoice.id,
            salesman_id=invoice.salesman_id,
            recovery_status='OVERDUE',
            risk_level='medium',
        )
        db.session.add(task)
        db.session.flush()  # assign task.id so it can be referenced below
        results['tasks_created'] += 1
        existing_task = task
    else:
        if existing_task.recovery_status == 'CLOSED_PAID':
            # Safety net: the invoice was paid & closed but is overdue again with an
            # outstanding balance (payment reversed/deleted in Sales via a path that
            # skipped Sale.update_status). Reopen it so it returns to recovery.
            # CLOSED_WRITTEN_OFF is left untouched — that is a deliberate admin call.
            existing_task.recovery_status = 'PARTIAL_RECOVERY' if invoice.status == 'partial' else 'OVERDUE'
            existing_task.closed_at = None
            existing_task.closed_reason = None
            existing_task.closed_by = None
            db.session.add(RecoveryLog(
                task_id=existing_task.id,
                response_type='general',
                note='Reopened: invoice has an outstanding balance again (payment reversed).',
            ))
        elif existing_task.recovery_status == 'PARTIAL_RECOVERY' and invoice.status == 'partial':
            pass  # keep as is
        elif existing_task.recovery_status not in (
            'PROMISED_PAYMENT', 'PARTIAL_RECOVERY', 'FOLLOW_UP_REQUIRED',
            'CLOSED_WRITTEN_OFF'
        ):
            existing_task.recovery_status = 'OVERDUE'

    # The Sales module's top-of-page overdue banner (see Sale.show_overdue_alert)
    # shows for days_overdue in [3, 5) and auto-hides after that 2-day window.
    # If admin never clicked "Done" to dismiss it, auto-escalate the recovery
    # task once the window closes so the invoice doesn't silently drop off
    # everyone's radar — same effect as the manual escalate action.
    if (invoice.days_overdue >= 5 and not invoice.overdue_alert_dismissed
            and not existing_task.is_escalated
            and existing_task.recovery_status not in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF')):
        invoice.overdue_alert_dismissed = True
        existing_task.is_escalated = True
        existing_task.escalated_at = datetime.utcnow()
        existing_task.risk_level = 'critical'
        existing_task.priority = 4
        existing_task.updated_at = datetime.utcnow()
        db.session.add(RecoveryLog(
            task_id=existing_task.id,
            response_type='escalated',
            note='Auto-escalated: overdue notification banner expired after 2 days without admin action.',
        ))


def _check_promise(task, today, results):
    if task.recovery_status != 'PROMISED_PAYMENT':
        return
    if not task.promise_date:
        return
    if task.promise_date < today:
        invoice = task.invoice
        if invoice and invoice.balance_due > 0:
            broken_date = task.promise_date
            task.recovery_status = 'FOLLOW_UP_REQUIRED'
            task.broken_promise_count = (task.broken_promise_count or 0) + 1
            task.last_broken_promise_date = broken_date
            task.priority = min(4, (task.priority or 1) + 1)
            log = RecoveryLog(
                task_id=task.id,
                response_type='no_response',
                promise_date=broken_date,
                promised_amount=task.promised_amount,
                note=(
                    f'Promise broken: customer promised to pay '
                    + (f'PKR {task.promised_amount:,.0f} ' if task.promised_amount else '')
                    + f'by {broken_date.strftime("%d-%m-%Y")} but the balance is still '
                    f'outstanding. Broken promise #{task.broken_promise_count}.'
                ),
            )
            db.session.add(log)
            results['promises_missed'] += 1


def _refresh_risk(task, results):
    new_risk = task.compute_risk_level()
    if new_risk != task.risk_level:
        task.risk_level = new_risk
        results['risk_updated'] += 1


# ─── Reminder helpers ─────────────────────────────────────────────────────────

_PRIORITY_MAP = {'low': 'Low', 'medium': 'Medium', 'high': 'High', 'critical': 'Critical'}


def _ensure_reminder(rtask, results=None):
    """Guarantee an open popup reminder exists for this recovery task's
    customer+salesman group (one popup covers all of that customer's open
    invoices for this salesman, not one per invoice). No-op if the salesman
    is not linked to a user, notifications are muted for this task, or a
    group reminder already exists."""
    if rtask.is_muted or rtask.is_on_hold:
        return  # notifications paused for this invoice (muted or on hold)

    salesman = rtask.salesman
    if not salesman or not salesman.user_id:
        return  # cannot target a login user — skip silently
    if not salesman.login_user or not salesman.login_user.is_active:
        return  # linked account is deactivated — it can't log in to see this

    invoice = rtask.invoice
    if not invoice or not invoice.customer_id:
        return

    from app.services.recovery_grouping import open_tasks_for_group, group_anchor_reminder, group_message

    group_tasks = [t for t in open_tasks_for_group(invoice.customer_id, rtask.salesman_id)
                   if not t.is_muted and not t.is_on_hold]
    if group_anchor_reminder(group_tasks):
        return  # this customer+salesman already has an open popup

    title, desc = group_message(group_tasks or [rtask])

    reminder = Task(
        title=title,
        description=desc,
        priority=_PRIORITY_MAP.get(rtask.risk_level, 'High'),
        reminder_at=pk_now(),                  # fire immediately on next poll
        assigned_to_id=salesman.user_id,
        created_by_id=salesman.user_id,        # system-generated, self-owned
        linked_invoice_id=rtask.invoice_id,
        recovery_task_id=rtask.id,
    )
    db.session.add(reminder)
    if results is not None:
        results['reminders_created'] = results.get('reminders_created', 0) + 1


def _cancel_reminders(rtask):
    """Stop any open reminders popping once the recovery task is closed/paid."""
    open_reminders = Task.query.filter(
        Task.recovery_task_id == rtask.id,
        Task.status.in_(['Pending', 'In Progress'])
    ).all()
    for r in open_reminders:
        r.status = 'Cancelled'
        r.is_notification_shown = True
        r.is_escalation_broadcast_shown = True
        r.is_completion_broadcast_shown = True


