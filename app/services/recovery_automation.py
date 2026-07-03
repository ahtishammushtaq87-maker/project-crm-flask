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
from app.models import Sale, RecoveryTask, RecoveryLog


def run_daily_automation():
    """Main entry point called by the daily job or manual trigger."""
    results = {
        'tasks_created': 0,
        'tasks_closed': 0,
        'promises_missed': 0,
        'risk_updated': 0,
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

    # Check promises on all open tasks
    open_tasks = RecoveryTask.query.filter(
        RecoveryTask.recovery_status.notin_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF'])
    ).all()

    for task in open_tasks:
        try:
            _check_promise(task, today, results)
            _refresh_risk(task, results)
        except Exception as e:
            results['errors'].append(f'Task {task.id}: {e}')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        results['errors'].append(f'Commit error: {e}')

    return results


def _process_invoice(invoice, today, results):
    due = invoice.due_date.date() if invoice.due_date and hasattr(invoice.due_date, 'date') else invoice.due_date

    existing_task = invoice.recovery_task

    if invoice.status == 'paid':
        if existing_task and existing_task.recovery_status not in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF'):
            existing_task.recovery_status = 'CLOSED_PAID'
            existing_task.closed_at = datetime.utcnow()
            results['tasks_closed'] += 1
        return

    if not due or today <= due:
        return  # not overdue yet — nothing to do

    if not existing_task:
        task = RecoveryTask(
            invoice_id=invoice.id,
            salesman_id=invoice.salesman_id,
            recovery_status='OVERDUE',
            risk_level='medium',
        )
        db.session.add(task)
        results['tasks_created'] += 1
    else:
        if existing_task.recovery_status == 'PARTIAL_RECOVERY' and invoice.status == 'partial':
            pass  # keep as is
        elif existing_task.recovery_status not in (
            'PROMISED_PAYMENT', 'PARTIAL_RECOVERY', 'FOLLOW_UP_REQUIRED',
            'CLOSED_PAID', 'CLOSED_WRITTEN_OFF'
        ):
            existing_task.recovery_status = 'OVERDUE'


def _check_promise(task, today, results):
    if task.recovery_status != 'PROMISED_PAYMENT':
        return
    if not task.promise_date:
        return
    if task.promise_date < today:
        invoice = task.invoice
        if invoice and invoice.balance_due > 0:
            task.recovery_status = 'FOLLOW_UP_REQUIRED'
            task.broken_promise_count = (task.broken_promise_count or 0) + 1
            task.priority = min(4, (task.priority or 1) + 1)
            log = RecoveryLog(
                task_id=task.id,
                response_type='no_response',
                note=f'Promise date {task.promise_date} passed with balance still outstanding. Broken promise #{task.broken_promise_count}.',
            )
            db.session.add(log)
            results['promises_missed'] += 1


def _refresh_risk(task, results):
    new_risk = task.compute_risk_level()
    if new_risk != task.risk_level:
        task.risk_level = new_risk
        results['risk_updated'] += 1


def close_task_paid(invoice):
    """Call this after a payment is posted and invoice balance drops to zero."""
    task = invoice.recovery_task
    if task and task.recovery_status not in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF'):
        task.recovery_status = 'CLOSED_PAID'
        task.closed_at = datetime.utcnow()
        db.session.commit()


def update_task_after_payment(invoice):
    """Call this after any payment is posted to keep task status in sync."""
    task = invoice.recovery_task
    if not task:
        return
    if invoice.balance_due <= 0:
        task.recovery_status = 'CLOSED_PAID'
        task.closed_at = datetime.utcnow()
    elif invoice.status == 'partial':
        if task.recovery_status not in ('PROMISED_PAYMENT', 'FOLLOW_UP_REQUIRED', 'CLOSED_PAID', 'CLOSED_WRITTEN_OFF'):
            task.recovery_status = 'PARTIAL_RECOVERY'
    db.session.commit()
