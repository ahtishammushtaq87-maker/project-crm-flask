import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from app import db
from app.models import RecoveryTask, RecoveryLog, Sale, Salesman, Customer, CustomerGroup, Task, User

bp = Blueprint('recovery', __name__)


def _require_recovery_view():
    if not (current_user.is_admin or current_user.can_view_recovery):
        flash('You do not have permission to view Sales Recovery.', 'danger')
        return redirect(url_for('dashboard.index'))
    return None


# ─── Dashboard ────────────────────────────────────────────────────────────────

@bp.route('/')
@login_required
def dashboard():
    guard = _require_recovery_view()
    if guard:
        return guard

    today = date.today()

    salesman_filter = request.args.get('salesman', '')
    customer_filter = request.args.get('customer', '')
    status_filter = request.args.get('status', '')
    risk_filter = request.args.get('risk', '')
    tab = request.args.get('tab', 'all')

    # Shared base query with the dropdown filters. Used for BOTH the table and
    # the KPI cards, so the cards reflect the same filter selection.
    base = RecoveryTask.query
    if customer_filter:
        base = base.join(Sale, RecoveryTask.invoice_id == Sale.id)
    if salesman_filter:
        base = base.filter(RecoveryTask.salesman_id == salesman_filter)
    if customer_filter:
        base = base.filter(Sale.customer_id == customer_filter)
    if status_filter:
        base = base.filter(RecoveryTask.recovery_status == status_filter)
    if risk_filter:
        base = base.filter(RecoveryTask.risk_level == risk_filter)

    # Table query = shared base + the active tab.
    q = base

    # Tab filters
    if tab == 'overdue':
        q = q.filter(RecoveryTask.recovery_status == 'OVERDUE')
    elif tab == 'partial':
        q = q.filter(RecoveryTask.recovery_status == 'PARTIAL_RECOVERY')
    elif tab == 'promise_today':
        q = q.filter(RecoveryTask.promise_date == today, RecoveryTask.recovery_status == 'PROMISED_PAYMENT')
    elif tab == 'promise_missed':
        q = q.filter(RecoveryTask.recovery_status == 'FOLLOW_UP_REQUIRED')
    elif tab == 'no_payment':
        q = q.filter(RecoveryTask.recovery_status.in_(['OVERDUE', 'FOLLOW_UP_REQUIRED']))
    elif tab == 'high_risk':
        q = q.filter(RecoveryTask.risk_level.in_(['high', 'critical']))
    elif tab == 'closed':
        q = q.filter(RecoveryTask.recovery_status.in_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF']))
    else:
        q = q.filter(RecoveryTask.recovery_status.notin_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF']))

    tasks = q.order_by(RecoveryTask.risk_level.desc(), RecoveryTask.updated_at.desc()).all()

    # KPIs — computed from the SAME filtered base (minus the tab), restricted to
    # open recovery tasks, so the top cards follow the applied filters.
    all_open = base.filter(
        RecoveryTask.recovery_status.notin_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF'])
    ).all()

    total_outstanding = sum(
        (t.invoice.balance_due if t.invoice else 0) for t in all_open
    )
    total_overdue = sum(
        (t.invoice.balance_due if t.invoice and t.invoice.is_overdue else 0) for t in all_open
    )
    partial_count = sum(1 for t in all_open if t.recovery_status == 'PARTIAL_RECOVERY')
    promise_today_count = sum(
        1 for t in all_open
        if t.promise_date == today and t.recovery_status == 'PROMISED_PAYMENT'
    )
    promise_missed_count = sum(1 for t in all_open if t.recovery_status == 'FOLLOW_UP_REQUIRED')
    escalated_count = sum(1 for t in all_open if t.is_escalated)

    salesmen = Salesman.query.filter_by(is_active=True).order_by(Salesman.name).all()
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all() \
        if hasattr(Customer, 'is_active') else Customer.query.order_by(Customer.name).all()

    return render_template(
        'recovery/dashboard.html',
        tasks=tasks,
        today=today,
        tab=tab,
        total_outstanding=total_outstanding,
        total_overdue=total_overdue,
        partial_count=partial_count,
        promise_today_count=promise_today_count,
        promise_missed_count=promise_missed_count,
        escalated_count=escalated_count,
        salesmen=salesmen,
        customers=customers,
        salesman_filter=salesman_filter,
        customer_filter=customer_filter,
        status_filter=status_filter,
        risk_filter=risk_filter,
    )


# ─── Salesman Radar ────────────────────────────────────────────────────────────

@bp.route('/radar')
@login_required
def radar():
    guard = _require_recovery_view()
    if guard:
        return guard

    today = date.today()

    q = RecoveryTask.query.filter(
        RecoveryTask.recovery_status.notin_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF'])
    )

    salesman_id = request.args.get('salesman', '')
    if not current_user.is_admin and salesman_id == '':
        pass  # show all for non-admin too (salesman linking is optional)
    if salesman_id:
        q = q.filter(RecoveryTask.salesman_id == salesman_id)

    tasks = q.all()

    def _bal(t):
        return t.invoice.balance_due if t.invoice else 0

    due_today = [t for t in tasks if t.next_follow_up_date == today]
    promise_missed = [t for t in tasks if t.recovery_status == 'FOLLOW_UP_REQUIRED']
    promise_today = [
        t for t in tasks
        if t.promise_date == today and t.recovery_status == 'PROMISED_PAYMENT'
    ]
    partial_balance = [t for t in tasks if t.recovery_status == 'PARTIAL_RECOVERY']
    no_payment = [t for t in tasks if t.last_payment_date is None and _bal(t) > 0]
    high_risk = [t for t in tasks if t.risk_level in ('high', 'critical')]

    salesmen = Salesman.query.filter_by(is_active=True).order_by(Salesman.name).all()

    return render_template(
        'recovery/radar.html',
        today=today,
        due_today=due_today,
        promise_missed=promise_missed,
        promise_today=promise_today,
        partial_balance=partial_balance,
        no_payment=no_payment,
        high_risk=high_risk,
        salesmen=salesmen,
        salesman_id=salesman_id,
    )


# ─── Task Detail ───────────────────────────────────────────────────────────────

@bp.route('/task/<int:task_id>')
@login_required
def task_detail(task_id):
    guard = _require_recovery_view()
    if guard:
        return guard

    task = RecoveryTask.query.get_or_404(task_id)
    today = date.today()
    staff_users = User.query.order_by(User.username).all()
    return render_template('recovery/task_detail.html', task=task, today=today, staff_users=staff_users)


# ─── Add Follow-up Log ─────────────────────────────────────────────────────────

@bp.route('/task/<int:task_id>/add-log', methods=['POST'])
@login_required
def add_log(task_id):
    if not (current_user.is_admin or current_user.can_add_recovery):
        flash('Permission denied.', 'danger')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    task = RecoveryTask.query.get_or_404(task_id)

    note = request.form.get('note', '').strip()
    response_type = request.form.get('response_type', 'general')
    next_follow_up_str = request.form.get('next_follow_up_date', '')
    next_follow_up = _parse_date(next_follow_up_str)

    if not note:
        flash('Note cannot be empty.', 'warning')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    log = RecoveryLog(
        task_id=task.id,
        response_type=response_type,
        note=note,
        next_follow_up_date=next_follow_up,
        logged_by=current_user.id,
    )
    db.session.add(log)

    if next_follow_up:
        task.next_follow_up_date = next_follow_up

    if response_type == 'no_response' and task.recovery_status not in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF'):
        task.recovery_status = 'FOLLOW_UP_REQUIRED'

    task.updated_at = datetime.utcnow()
    db.session.commit()

    flash('Follow-up log added.', 'success')
    return redirect(url_for('recovery.task_detail', task_id=task_id))


# ─── Mark Promise ──────────────────────────────────────────────────────────────

@bp.route('/task/<int:task_id>/mark-promise', methods=['POST'])
@login_required
def mark_promise(task_id):
    if not (current_user.is_admin or current_user.can_add_recovery):
        flash('Permission denied.', 'danger')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    task = RecoveryTask.query.get_or_404(task_id)

    promise_date_str = request.form.get('promise_date', '')
    promised_amount_str = request.form.get('promised_amount', '0')
    note = request.form.get('note', '').strip()

    promise_dt = _parse_datetime(promise_date_str)   # date OR date+time
    try:
        promised_amount = float(promised_amount_str)
    except (ValueError, TypeError):
        promised_amount = 0

    if not promise_dt:
        flash('Promise date is required.', 'warning')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    promise_date = promise_dt.date()

    task.recovery_status = 'PROMISED_PAYMENT'
    task.promise_date = promise_date
    task.promised_amount = promised_amount
    task.next_follow_up_date = promise_date
    task.updated_at = datetime.utcnow()

    # Re-arm the popup reminder to fire again at the promised date/time.
    _rearm_reminder(task, promise_dt)

    log = RecoveryLog(
        task_id=task.id,
        response_type='promised_payment',
        note=note or f'Customer promised PKR {promised_amount:,.0f} by {promise_dt.strftime("%d-%m-%Y %H:%M")}.',
        promised_amount=promised_amount,
        promise_date=promise_date,
        next_follow_up_date=promise_date,
        logged_by=current_user.id,
    )
    db.session.add(log)
    db.session.commit()

    flash('Promise recorded. A reminder will pop up again at the promised time.', 'success')
    return redirect(url_for('recovery.task_detail', task_id=task_id))


# ─── Escalate ─────────────────────────────────────────────────────────────────

@bp.route('/task/<int:task_id>/escalate', methods=['POST'])
@login_required
def escalate_task(task_id):
    if not (current_user.is_admin or current_user.can_edit_recovery):
        flash('Permission denied.', 'danger')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    task = RecoveryTask.query.get_or_404(task_id)
    note = request.form.get('note', 'Task escalated by ' + current_user.username)

    task.is_escalated = True
    task.escalated_at = datetime.utcnow()
    task.risk_level = 'critical'
    task.priority = 4
    task.updated_at = datetime.utcnow()

    log = RecoveryLog(
        task_id=task.id,
        response_type='escalated',
        note=note,
        logged_by=current_user.id,
    )
    db.session.add(log)
    db.session.commit()

    flash('Task escalated.', 'warning')
    return redirect(url_for('recovery.task_detail', task_id=task_id))


# ─── Close with Reason ────────────────────────────────────────────────────────

@bp.route('/task/<int:task_id>/close', methods=['POST'])
@login_required
def close_task(task_id):
    if not (current_user.is_admin or current_user.can_edit_recovery):
        flash('Permission denied.', 'danger')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    task = RecoveryTask.query.get_or_404(task_id)
    reason = request.form.get('reason', '').strip()
    close_type = request.form.get('close_type', 'CLOSED_WRITTEN_OFF')

    if not reason:
        flash('Closing reason is required.', 'warning')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    task.recovery_status = close_type
    task.closed_reason = reason
    task.closed_at = datetime.utcnow()
    task.closed_by = current_user.id
    task.updated_at = datetime.utcnow()

    log = RecoveryLog(
        task_id=task.id,
        response_type='general',
        note=f'Task closed ({close_type}): {reason}',
        logged_by=current_user.id,
    )
    db.session.add(log)
    db.session.commit()

    flash('Recovery task closed.', 'success')
    return redirect(url_for('recovery.dashboard'))


# ─── Send Reminder (log + optional scheduled popup alarm) ─────────────────────

@bp.route('/task/<int:task_id>/send-reminder', methods=['POST'])
@login_required
def send_reminder(task_id):
    if not (current_user.is_admin or current_user.can_add_recovery):
        flash('Permission denied.', 'danger')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    task = RecoveryTask.query.get_or_404(task_id)
    channel = request.form.get('channel', 'phone')
    note = request.form.get('note', '').strip()
    customer_name = task.invoice.customer.name if task.invoice and task.invoice.customer else 'the customer'

    message = f'Call this {customer_name}.'
    if note:
        message += f' Note: {note}'

    # Both fields are optional: without a date/time AND at least one assigned
    # user, this behaves exactly as before (a plain audit log, no popup).
    reminder_at = None
    reminder_at_str = request.form.get('reminder_at', '').strip()
    if reminder_at_str:
        try:
            reminder_at = datetime.strptime(reminder_at_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            reminder_at = None

    requested_user_ids = {int(i) for i in request.form.getlist('user_ids[]') if i.strip().isdigit()}

    scheduled_users = []
    batch_id = None
    if reminder_at and requested_user_ids:
        # A shared batch id lets one user's "Complete Task" clear the reminder
        # for every other assigned user too (bulk selection), and lets the
        # Conversation Log entry below show a live countdown / completed status.
        batch_id = str(uuid.uuid4())
        for user in User.query.filter(User.id.in_(requested_user_ids)).all():
            db.session.add(Task(
                title=f'Recovery Reminder: {customer_name}',
                description=message,
                priority='High',
                reminder_at=reminder_at,
                assigned_to_id=user.id,
                created_by_id=current_user.id,
                linked_invoice_id=task.invoice_id,
                recovery_task_id=task.id,
                reminder_batch_id=batch_id,
            ))
            scheduled_users.append(user.username)

    log_note = f'Payment reminder via {channel}: {message}'
    if scheduled_users:
        log_note += f' (Popup scheduled for {reminder_at.strftime("%Y-%m-%d %H:%M")} — assigned to: {", ".join(scheduled_users)})'
    elif note:
        log_note = f'Payment reminder via {channel}: {note}'

    log = RecoveryLog(
        task_id=task.id,
        response_type='general',
        note=log_note,
        logged_by=current_user.id,
        reminder_batch_id=batch_id,
    )
    db.session.add(log)
    task.updated_at = datetime.utcnow()
    db.session.commit()

    if scheduled_users:
        flash(f'Reminder scheduled for {reminder_at.strftime("%Y-%m-%d %H:%M")} — assigned to: {", ".join(scheduled_users)}.', 'success')
    else:
        flash('Reminder logged.', 'success')
    return redirect(url_for('recovery.task_detail', task_id=task_id))


# ─── Recovery Reminder Broadcasts (admin-only, site-wide) ─────────────────────

def _parse_client_time():
    """Match the same browser-local time convention used by users.poll_tasks,
    so escalation/completion timing stays consistent regardless of the
    server's own clock/timezone after deployment."""
    client_time_str = request.args.get('client_time')
    if client_time_str:
        try:
            clean_time = client_time_str.split('Z')[0].split('+')[0]
            return datetime.fromisoformat(clean_time)
        except Exception:
            pass
    return datetime.now()


@bp.route('/broadcasts/poll')
@login_required
def poll_broadcasts():
    if not current_user.is_admin:
        return jsonify([])

    now = _parse_client_time()
    messages = []

    # Escalation: reminder was raised 8+ hours ago and is still not complete.
    # Anchored on created_at (a stable point) rather than reminder_at, because
    # each 1-minute "snooze" pushes reminder_at forward and would otherwise
    # keep resetting the 8-hour SLA so it never fires.
    overdue_candidates = Task.query.filter(
        Task.recovery_task_id.isnot(None),
        Task.status.in_(['Pending', 'In Progress']),
        Task.is_escalation_broadcast_shown == False
    ).all()
    for t in overdue_candidates:
        anchor = t.created_at or t.reminder_at
        if anchor and datetime.utcnow() >= anchor + timedelta(hours=8):
            inv = t.recovery_task.invoice if t.recovery_task else None
            customer_name = inv.customer.name if inv and inv.customer else 'the customer'
            messages.append({
                'id': t.id,
                'kind': 'escalation',
                'text': f'{t.assigned_to.username} could not call this {customer_name}.'
            })

    # Completion: reminder was completed and hasn't been announced yet.
    completed_candidates = Task.query.filter(
        Task.recovery_task_id.isnot(None),
        Task.status == 'Completed',
        Task.is_completion_broadcast_shown == False
    ).all()
    for t in completed_candidates:
        inv = t.recovery_task.invoice if t.recovery_task else None
        customer_name = inv.customer.name if inv and inv.customer else 'the customer'
        messages.append({
            'id': t.id,
            'kind': 'completion',
            'text': f'Task complete: {t.assigned_to.username} called this {customer_name}.'
        })

    return jsonify(messages)


@bp.route('/broadcasts/dismiss/<int:task_id>', methods=['POST'])
@login_required
def dismiss_broadcast(task_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    kind = request.form.get('kind')
    task = Task.query.get_or_404(task_id)

    if kind == 'escalation':
        task.is_escalation_broadcast_shown = True
    elif kind == 'completion':
        task.is_completion_broadcast_shown = True

    db.session.commit()
    return jsonify({'success': True})


# ─── Live Reminder Popup Actions (called from the global alarm popup) ─────────

def _client_now_from_form():
    """Browser-local 'now' posted from the popup, matching poll_tasks' clock."""
    ct = request.form.get('client_time')
    if ct:
        try:
            return datetime.fromisoformat(ct.split('Z')[0].split('+')[0])
        except Exception:
            pass
    return datetime.now()


@bp.route('/reminder/<int:reminder_id>/snooze', methods=['POST'])
@login_required
def reminder_snooze(reminder_id):
    """Dismiss without completing → re-show again in 1 minute (until done)."""
    reminder = Task.query.get_or_404(reminder_id)
    if not reminder.recovery_task_id:
        return jsonify({'success': False, 'message': 'Not a recovery reminder'}), 400
    if current_user.role != 'admin' and reminder.assigned_to_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    reminder.reminder_at = _client_now_from_form() + timedelta(minutes=1)
    reminder.is_notification_shown = False
    reminder.is_email_sent = True  # don't re-email on every 1-min re-show
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/reminder/<int:reminder_id>/promise', methods=['POST'])
@login_required
def reminder_promise(reminder_id):
    """Capture the promised date + amount from the popup, snooze the reminder
    until that date, and update the recovery task accordingly."""
    reminder = Task.query.get_or_404(reminder_id)
    if not reminder.recovery_task_id:
        return jsonify({'success': False, 'message': 'Not a recovery reminder'}), 400
    if current_user.role != 'admin' and reminder.assigned_to_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    rtask = reminder.recovery_task
    promise_dt = _parse_datetime(request.form.get('promise_date', ''))   # date OR date+time
    try:
        promised_amount = float(request.form.get('promised_amount', '0') or 0)
    except (ValueError, TypeError):
        promised_amount = 0

    if not promise_dt:
        return jsonify({'success': False, 'message': 'Promise date is required'}), 400

    promise_date = promise_dt.date()

    rtask.recovery_status = 'PROMISED_PAYMENT'
    rtask.promise_date = promise_date
    rtask.promised_amount = promised_amount
    rtask.next_follow_up_date = promise_date
    rtask.updated_at = datetime.utcnow()

    # Re-arm this reminder to fire again at the exact promised date/time.
    reminder.reminder_at = promise_dt
    reminder.is_notification_shown = False
    reminder.is_email_sent = False

    db.session.add(RecoveryLog(
        task_id=rtask.id,
        response_type='promised_payment',
        note=f'{current_user.username} recorded a promise: PKR {promised_amount:,.0f} by {promise_dt.strftime("%d-%m-%Y %H:%M")}.',
        promised_amount=promised_amount,
        promise_date=promise_date,
        next_follow_up_date=promise_date,
        logged_by=current_user.id,
    ))
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/reminder/<int:reminder_id>/complete', methods=['POST'])
@login_required
def reminder_complete(reminder_id):
    """Mark the reminder complete (payment collected / resolved). Triggers the
    admin 'task complete' broadcast and logs it on the recovery task."""
    reminder = Task.query.get_or_404(reminder_id)
    if not reminder.recovery_task_id:
        return jsonify({'success': False, 'message': 'Not a recovery reminder'}), 400
    if current_user.role != 'admin' and reminder.assigned_to_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    reminder.status = 'Completed'
    reminder.is_notification_shown = True

    rtask = reminder.recovery_task
    if rtask:
        db.session.add(RecoveryLog(
            task_id=rtask.id,
            response_type='general',
            note=f'{current_user.username} marked the recovery reminder complete.',
            logged_by=current_user.id,
        ))
    db.session.commit()
    return jsonify({'success': True})


# ─── Run Automation (admin) ───────────────────────────────────────────────────

@bp.route('/run-automation', methods=['POST'])
@login_required
def run_automation():
    if not current_user.is_admin:
        flash('Admin only.', 'danger')
        return redirect(url_for('recovery.dashboard'))

    from app.services.recovery_automation import run_daily_automation
    results = run_daily_automation()

    flash(
        f"Automation complete: {results['tasks_created']} created, "
        f"{results['tasks_closed']} closed, "
        f"{results.get('reminders_created', 0)} reminders raised, "
        f"{results['promises_missed']} promises missed, "
        f"{results['risk_updated']} risk levels updated."
        + (f" Errors: {len(results['errors'])}" if results['errors'] else ''),
        'success' if not results['errors'] else 'warning'
    )
    return redirect(url_for('recovery.dashboard'))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_date(s):
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(s):
    """Parse a promise value that may be a date OR a date+time (from a
    datetime-local picker). Returns a datetime; date-only defaults to 09:00."""
    if not s:
        return None
    s = s.strip()
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M',
                '%Y-%m-%d %H:%M:%S', '%d-%m-%Y %H:%M'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    d = _parse_date(s)
    if d:
        return datetime.combine(d, datetime.min.time()).replace(hour=9)
    return None


def _rearm_reminder(rtask, when_dt):
    """Make a popup reminder for this recovery task fire at `when_dt`.
    Re-arms an existing open reminder, or creates one for the linked user."""
    reminder = Task.query.filter(
        Task.recovery_task_id == rtask.id,
        Task.status.in_(['Pending', 'In Progress'])
    ).order_by(Task.reminder_at.asc()).first()

    if reminder:
        reminder.reminder_at = when_dt
        reminder.is_notification_shown = False
        reminder.is_email_sent = False
        return reminder

    salesman = rtask.salesman
    if not salesman or not salesman.user_id:
        return None

    invoice = rtask.invoice
    customer_name = invoice.customer.name if invoice and invoice.customer else 'the customer'
    inv_no = invoice.invoice_number if invoice else '—'
    balance = invoice.balance_due if invoice else 0
    reminder = Task(
        title=f'Recovery: Call {customer_name}',
        description=(f'Invoice {inv_no} is overdue. Balance PKR {balance:,.0f}. '
                     f'Call {customer_name} and record their promised date & amount.'),
        priority='High',
        reminder_at=when_dt,
        assigned_to_id=salesman.user_id,
        created_by_id=salesman.user_id,
        linked_invoice_id=rtask.invoice_id,
        recovery_task_id=rtask.id,
    )
    db.session.add(reminder)
    return reminder
