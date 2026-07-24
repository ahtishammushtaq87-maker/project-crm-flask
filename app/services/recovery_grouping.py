"""
Sales Recovery grouping helpers.

A customer can have several overdue invoices at once, each with its own
RecoveryTask row. These helpers let the dashboard and the popup-reminder
system treat all of a customer's open invoices as one group: one combined
promise date, and one popup notification instead of one per invoice.
"""

from datetime import datetime
from app import db
from app.models import RecoveryTask, Sale, Task

OPEN_STATUSES = ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF')

# In the Sales module an invoice has no dedicated "cancelled" status; a cancel
# is recorded as is_rejected=True with this exact rejection reason (see
# app/routes/sales.py). A draft is is_draft=True. Recovery should ignore both.
CANCELLED_REASON = 'Cancelled by Admin'


def active_invoice_criterion():
    """SQLAlchemy condition (on the Sale/invoice) selecting invoices that are
    neither a draft nor cancelled in the Sales module. Use with an explicit
    Sale join, or wrapped in RecoveryTask.invoice.has(...)."""
    return db.and_(
        Sale.is_draft == False,
        db.not_(db.and_(Sale.is_rejected == True,
                        Sale.rejection_reason == CANCELLED_REASON))
    )


def exclude_draft_cancelled(query):
    """Filter a RecoveryTask query so tasks whose invoice is a draft or was
    cancelled in Sales are hidden. Does not require an existing Sale join."""
    return query.filter(RecoveryTask.invoice.has(active_invoice_criterion()))


def open_tasks_for_customer(customer_id):
    """All open (non-closed) RecoveryTasks for this customer, across all
    salesmen. Excludes invoices that are drafts or cancelled in Sales."""
    return RecoveryTask.query.join(Sale, RecoveryTask.invoice_id == Sale.id).filter(
        Sale.customer_id == customer_id,
        RecoveryTask.recovery_status.notin_(OPEN_STATUSES),
        active_invoice_criterion()
    ).all()


def open_tasks_for_group(customer_id, salesman_id):
    """Open RecoveryTasks for this customer, narrowed to one exact salesman
    (including tasks with no salesman at all, when salesman_id is None) — the
    consolidation key for a single popup reminder. A reminder is assigned to
    one user, so this must never merge invoices belonging to a different
    salesman's book, even when the triggering task itself has no salesman."""
    tasks = open_tasks_for_customer(customer_id)
    return [t for t in tasks if t.salesman_id == salesman_id]


def group_message(tasks):
    """Build the popup Task's title/description for a group of RecoveryTasks
    belonging to the same customer (+ salesman)."""
    invs = [t.invoice for t in tasks if t.invoice]
    total_balance = sum(i.balance_due for i in invs)
    customer_name = invs[0].customer.name if invs and invs[0].customer else 'the customer'

    if len(invs) <= 1:
        inv = invs[0] if invs else None
        title = f'Recovery: Call {customer_name}'
        if inv:
            desc = (f'Invoice {inv.invoice_number} is overdue. Balance PKR {total_balance:,.0f}. '
                    f'Call {customer_name} and record their promised date & amount.')
        else:
            desc = f'Call {customer_name} and record their promised date & amount.'
        return title, desc

    inv_list = ', '.join(i.invoice_number for i in invs)
    title = f'Recovery: Call {customer_name} ({len(invs)} overdue invoices)'
    desc = (f'{len(invs)} overdue invoices ({inv_list}). Total balance PKR {total_balance:,.0f}. '
            f'Call {customer_name} and record their promised date & amount.')
    return title, desc


def group_anchor_reminder(tasks):
    """The single open popup Task representing this group, if one exists."""
    ids = [t.id for t in tasks]
    if not ids:
        return None
    return Task.query.filter(
        Task.recovery_task_id.in_(ids),
        Task.status.in_(['Pending', 'In Progress'])
    ).order_by(Task.reminder_at.asc()).first()


def rearm_group_reminder(tasks, when_dt):
    """Ensure exactly one open popup reminder exists for this group of
    RecoveryTasks, scheduled at when_dt. Reuses/updates the earliest existing
    open reminder in the group as the anchor, cancels any stray duplicates
    (e.g. left over from before consolidation), or creates one new Task if
    none exists yet. Returns the anchor Task, or None if it can't be created
    (no salesman/login user linked)."""
    ids = [t.id for t in tasks]
    if not ids:
        return None

    open_reminders = Task.query.filter(
        Task.recovery_task_id.in_(ids),
        Task.status.in_(['Pending', 'In Progress'])
    ).order_by(Task.reminder_at.asc()).all()

    if open_reminders:
        anchor = open_reminders[0]
        for extra in open_reminders[1:]:
            extra.status = 'Cancelled'
            extra.is_notification_shown = True
        anchor.reminder_at = when_dt
        anchor.is_notification_shown = False
        anchor.is_email_sent = False
        return anchor

    primary = tasks[0]
    salesman = primary.salesman
    if not salesman or not salesman.user_id:
        return None

    title, desc = group_message(tasks)
    reminder = Task(
        title=title,
        description=desc,
        priority='High',
        reminder_at=when_dt,
        assigned_to_id=salesman.user_id,
        created_by_id=salesman.user_id,
        linked_invoice_id=primary.invoice_id,
        recovery_task_id=primary.id,
    )
    db.session.add(reminder)
    return reminder


def cancel_group_reminders(tasks):
    """Cancel all open popup reminders for a group (used when the whole
    group is closed)."""
    ids = [t.id for t in tasks]
    if not ids:
        return
    for r in Task.query.filter(
        Task.recovery_task_id.in_(ids),
        Task.status.in_(['Pending', 'In Progress'])
    ).all():
        r.status = 'Cancelled'
        r.is_notification_shown = True
        r.is_escalation_broadcast_shown = True
        r.is_completion_broadcast_shown = True
