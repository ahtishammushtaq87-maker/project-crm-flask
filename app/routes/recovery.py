import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from app import db
from app.models import RecoveryTask, RecoveryLog, RecoveryComment, Sale, Salesman, Customer, CustomerGroup, Task, User
from app.services.recovery_grouping import (
    open_tasks_for_customer, open_tasks_for_group, rearm_group_reminder,
    cancel_group_reminders, exclude_draft_cancelled, active_invoice_criterion,
    CANCELLED_REASON,
)
from app.utils import pk_now

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
    invoice_filter = request.args.get('invoice', '')
    status_filter = request.args.get('status', '')
    risk_filter = request.args.get('risk', '')
    tab = request.args.get('tab', 'all')

    # Shared base query with the dropdown filters. Used for BOTH the table and
    # the KPI cards, so the cards reflect the same filter selection.
    # Hide invoices that are drafts or cancelled in the Sales module.
    base = exclude_draft_cancelled(RecoveryTask.query)
    if customer_filter or invoice_filter:
        base = base.join(Sale, RecoveryTask.invoice_id == Sale.id)
    if salesman_filter:
        base = base.filter(RecoveryTask.salesman_id == salesman_filter)
    if customer_filter:
        base = base.filter(Sale.customer_id == customer_filter)
    if invoice_filter:
        base = base.filter(Sale.id == invoice_filter)
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
    elif tab == 'on_hold':
        q = q.filter(RecoveryTask.is_on_hold == True,
                     RecoveryTask.recovery_status.notin_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF']))
    elif tab == 'closed':
        q = q.filter(RecoveryTask.recovery_status.in_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF']))
    else:
        q = q.filter(RecoveryTask.recovery_status.notin_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF']))

    tasks = q.order_by(RecoveryTask.risk_level.desc(), RecoveryTask.updated_at.desc()).all()
    # Guard against duplicate RecoveryTask rows for the same invoice (a data
    # glitch that otherwise shows an invoice twice and double-counts the group
    # totals). Keep the most urgent/recent one — the list is already sorted.
    tasks = _dedupe_by_invoice(tasks)

    customer_groups = _group_tasks_by_customer(tasks)

    # KPIs — computed from the SAME filtered base (minus the tab), restricted to
    # open recovery tasks, so the top cards follow the applied filters.
    all_open = _dedupe_by_invoice(base.filter(
        RecoveryTask.recovery_status.notin_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF'])
    ).all())

    total_outstanding = sum(
        (t.invoice.balance_due if t.invoice else 0) for t in all_open
    )
    total_overdue = sum(
        (t.invoice.overdue_amount if t.invoice else 0) for t in all_open
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
    invoices = Sale.query.join(RecoveryTask, RecoveryTask.invoice_id == Sale.id) \
        .filter(active_invoice_criterion()) \
        .order_by(Sale.invoice_number.desc()).all()

    return render_template(
        'recovery/dashboard.html',
        tasks=tasks,
        customer_groups=customer_groups,
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
        invoices=invoices,
        salesman_filter=salesman_filter,
        customer_filter=customer_filter,
        invoice_filter=invoice_filter,
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

    q = exclude_draft_cancelled(RecoveryTask.query).filter(
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

    # This customer's other open invoices — shown alongside this one since a
    # promise date set here (or from the dashboard) covers all of them.
    sibling_tasks = []
    group_balance = task.invoice.balance_due if task.invoice else 0
    if task.invoice and task.invoice.customer_id:
        sibling_tasks = [
            t for t in open_tasks_for_customer(task.invoice.customer_id) if t.id != task.id
        ]
        group_balance += sum(t.invoice.balance_due for t in sibling_tasks if t.invoice)

    # One popup reminder is shared across the whole customer group (see
    # recovery_grouping), so the "Next Reminder" shown here should reflect
    # the group's soonest reminder, not just this one task's own link.
    reminder_times = [t.next_reminder_at for t in ([task] + sibling_tasks) if t.next_reminder_at]
    group_next_reminder = min(reminder_times) if reminder_times else None

    return render_template(
        'recovery/task_detail.html', task=task, today=today, staff_users=staff_users,
        sibling_tasks=sibling_tasks, group_balance=group_balance,
        group_next_reminder=group_next_reminder,
    )


# ─── Customer Group Detail (combined totals for all of a customer's invoices) ──

@bp.route('/group/<int:customer_id>')
@login_required
def group_detail(customer_id):
    """A recovery detail page for a whole customer group. Unlike the per-invoice
    task detail, the summary here shows the COMBINED totals (total invoice, total
    paid, total balance, total overdue) across every open recovery invoice of the
    customer, plus each invoice and one merged conversation log."""
    guard = _require_recovery_view()
    if guard:
        return guard

    customer = Customer.query.get_or_404(customer_id)
    today = date.today()

    # The group = this customer's open recovery invoices (drafts/cancelled/
    # fully-paid already excluded), deduped so a duplicate task never counts twice.
    tasks = _dedupe_by_invoice(open_tasks_for_customer(customer_id))
    tasks.sort(key=lambda t: (_RISK_RANK.get(t.risk_level, 0),
                              t.updated_at or datetime.min), reverse=True)

    invs = [t.invoice for t in tasks if t.invoice]
    totals = {
        'total':          sum(i.total for i in invs),
        'paid':           sum(i.paid_amount for i in invs),
        'balance':        sum(i.balance_due for i in invs),
        'overdue_amount': sum(i.overdue_amount for i in invs),
        'invoice_count':  len(tasks),
    }
    worst_risk = max((t.risk_level for t in tasks),
                     key=lambda r: _RISK_RANK.get(r, 0), default='low')
    any_escalated = any(t.is_escalated for t in tasks)
    any_on_hold = any(t.is_on_hold for t in tasks)
    promise_dates = [t.promise_date for t in tasks if t.promise_date]
    earliest_promise = min(promise_dates) if promise_dates else None
    reminder_times = [t.next_reminder_at for t in tasks if t.next_reminder_at]
    group_next_reminder = min(reminder_times) if reminder_times else None
    follow_dates = [t.next_follow_up_date for t in tasks if t.next_follow_up_date]
    earliest_follow_up = min(follow_dates) if follow_dates else None

    # Combined broken-promise history across every invoice in the group.
    broken_count = sum((t.broken_promise_count or 0) for t in tasks)
    combined_broken = []
    for t in tasks:
        for bp in (t.broken_promises or []):
            row = dict(bp)
            row['invoice'] = t.invoice.invoice_number if t.invoice else None
            combined_broken.append(row)
    combined_broken.sort(key=lambda b: b.get('date') or date.min, reverse=True)

    # One merged conversation log across all the group's invoices, newest first.
    combined_logs = sorted(
        (log for t in tasks for log in t.logs),
        key=lambda l: l.created_at or datetime.min, reverse=True
    )
    last_note = combined_logs[0].note if combined_logs else None

    # Combined comment thread across the group, newest first.
    combined_comments = sorted(
        (c for t in tasks for c in t.comments),
        key=lambda c: c.created_at or datetime.min, reverse=True
    )

    open_tasks = [t for t in tasks
                  if t.recovery_status not in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF')]
    all_on_hold = bool(open_tasks) and all(t.is_on_hold for t in open_tasks)
    is_open = bool(open_tasks)

    return render_template(
        'recovery/group_detail.html',
        customer=customer, today=today, tasks=tasks, totals=totals,
        worst_risk=worst_risk, any_escalated=any_escalated, any_on_hold=any_on_hold,
        all_on_hold=all_on_hold, is_open=is_open,
        earliest_promise=earliest_promise, group_next_reminder=group_next_reminder,
        earliest_follow_up=earliest_follow_up, broken_count=broken_count,
        combined_broken=combined_broken, combined_logs=combined_logs, last_note=last_note,
        combined_comments=combined_comments,
    )


# ─── Customer Group Actions (apply one action to all of a customer's invoices) ──

def _open_group_tasks(customer_id):
    """All open recovery tasks for a customer, deduped by invoice."""
    tasks = _dedupe_by_invoice(open_tasks_for_customer(customer_id))
    return [t for t in tasks
            if t.recovery_status not in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF')]


@bp.route('/group/<int:customer_id>/toggle-hold', methods=['POST'])
@login_required
def group_toggle_hold(customer_id):
    """Put every open invoice in the group On Hold, or take them all off hold."""
    if not (current_user.is_admin or current_user.can_edit_recovery):
        flash('Permission denied.', 'danger')
        return redirect(url_for('recovery.group_detail', customer_id=customer_id))

    from app.services.recovery_automation import _ensure_reminder
    all_tasks = _dedupe_by_invoice(open_tasks_for_customer(customer_id))
    open_tasks = [t for t in all_tasks
                  if t.recovery_status not in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF')]
    if not open_tasks:
        flash('No open invoices to hold.', 'warning')
        return redirect(url_for('recovery.group_detail', customer_id=customer_id))

    turn_on = not all(t.is_on_hold for t in open_tasks)
    now = datetime.utcnow()
    for t in open_tasks:
        t.is_on_hold = turn_on
        t.updated_at = now
        if turn_on:
            t.on_hold_at, t.on_hold_by = now, current_user.id
        else:
            t.on_hold_at, t.on_hold_by = None, None
        db.session.add(RecoveryLog(
            task_id=t.id, response_type='general',
            note=f'Invoice {"put On Hold" if turn_on else "taken off hold"} '
                 f'(group action) by {current_user.username}.',
            logged_by=current_user.id,
        ))

    if turn_on:
        cancel_group_reminders(all_tasks)   # stop all popups/timers for the group
    else:
        for t in open_tasks:
            if not t.is_muted:
                _ensure_reminder(t)

    db.session.commit()
    flash(f'{"Put all invoices On Hold" if turn_on else "Took all invoices off hold"} '
          f'({len(open_tasks)}).', 'success')
    return redirect(url_for('recovery.group_detail', customer_id=customer_id))


@bp.route('/group/<int:customer_id>/close', methods=['POST'])
@login_required
def group_close(customer_id):
    """Close every open invoice in the group with one reason."""
    if not (current_user.is_admin or current_user.can_edit_recovery):
        flash('Permission denied.', 'danger')
        return redirect(url_for('recovery.group_detail', customer_id=customer_id))

    reason = request.form.get('reason', '').strip()
    close_type = request.form.get('close_type', 'CLOSED_WRITTEN_OFF')
    if not reason:
        flash('Closing reason is required.', 'warning')
        return redirect(url_for('recovery.group_detail', customer_id=customer_id))

    all_tasks = _dedupe_by_invoice(open_tasks_for_customer(customer_id))
    open_tasks = [t for t in all_tasks
                  if t.recovery_status not in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF')]
    now = datetime.utcnow()
    for t in open_tasks:
        t.recovery_status = close_type
        t.closed_reason = reason
        t.closed_at = now
        t.closed_by = current_user.id
        t.updated_at = now
        db.session.add(RecoveryLog(
            task_id=t.id, response_type='general',
            note=f'Task closed ({close_type}) (group action): {reason}',
            logged_by=current_user.id,
        ))
    cancel_group_reminders(all_tasks)
    db.session.commit()
    flash(f'Closed {len(open_tasks)} invoice(s).', 'success')
    return redirect(url_for('recovery.dashboard'))


@bp.route('/group/<int:customer_id>/add-log', methods=['POST'])
@login_required
def group_add_log(customer_id):
    """Add one follow-up message to every open invoice in the group."""
    if not (current_user.is_admin or current_user.can_add_recovery):
        flash('Permission denied.', 'danger')
        return redirect(url_for('recovery.group_detail', customer_id=customer_id))

    note = request.form.get('note', '').strip()
    response_type = request.form.get('response_type', 'general')
    next_follow_up = _parse_date(request.form.get('next_follow_up_date', ''))
    if not note:
        flash('Note cannot be empty.', 'warning')
        return redirect(url_for('recovery.group_detail', customer_id=customer_id))

    open_tasks = _open_group_tasks(customer_id)
    now = datetime.utcnow()
    for t in open_tasks:
        db.session.add(RecoveryLog(
            task_id=t.id, response_type=response_type, note=note,
            next_follow_up_date=next_follow_up, logged_by=current_user.id,
        ))
        if next_follow_up:
            t.next_follow_up_date = next_follow_up
        if response_type == 'no_response':
            t.recovery_status = 'FOLLOW_UP_REQUIRED'
        t.updated_at = now

    db.session.commit()
    flash(f'Message added to {len(open_tasks)} invoice(s).', 'success')
    return redirect(url_for('recovery.group_detail', customer_id=customer_id))


@bp.route('/group/<int:customer_id>/add-comment', methods=['POST'])
@login_required
def group_add_comment(customer_id):
    """Add a comment to the group (recorded against its most-urgent invoice)."""
    if not (current_user.is_admin or current_user.can_add_recovery):
        flash('Permission denied.', 'danger')
        return redirect(url_for('recovery.group_detail', customer_id=customer_id))

    text = request.form.get('comment', '').strip()
    if not text:
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('recovery.group_detail', customer_id=customer_id))

    tasks = _dedupe_by_invoice(open_tasks_for_customer(customer_id))
    tasks.sort(key=lambda t: (_RISK_RANK.get(t.risk_level, 0),
                              t.updated_at or datetime.min), reverse=True)
    if not tasks:
        flash('No open invoices for this customer.', 'warning')
        return redirect(url_for('recovery.group_detail', customer_id=customer_id))

    db.session.add(RecoveryComment(
        task_id=tasks[0].id, comment=text, created_by=current_user.id,
    ))
    db.session.commit()
    flash('Comment added.', 'success')
    return redirect(url_for('recovery.group_detail', customer_id=customer_id))


@bp.route('/group/<int:customer_id>/pdf')
@login_required
def group_pdf(customer_id):
    """Combined recovery PDF for a whole customer group — same invoice-styled
    chrome as the per-invoice PDF, but with the group's combined totals, all its
    invoices and one merged activity log."""
    guard = _require_recovery_view()
    if guard:
        return guard

    import io
    from flask import send_file
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
    from app.models import Company, InvoiceSettings
    from app.pdf_utils import (
        ProfessionalPDFGenerator, PRIMARY_COLOR, TEXT_COLOR, MUTED_TEXT,
        BORDER_GREY, HEADER_STRIPE, WHITE,
    )

    customer = Customer.query.get_or_404(customer_id)
    company = Company.query.first()
    invoice_settings = InvoiceSettings.query.first()

    tasks = _dedupe_by_invoice(open_tasks_for_customer(customer_id))
    tasks.sort(key=lambda t: (_RISK_RANK.get(t.risk_level, 0),
                              t.updated_at or datetime.min), reverse=True)
    invs = [t.invoice for t in tasks if t.invoice]
    total = sum(i.total for i in invs)
    paid = sum(i.paid_amount for i in invs)
    balance = sum(i.balance_due for i in invs)
    overdue_amount = sum(i.overdue_amount for i in invs)

    def d(dt, fmt='%d-%m-%Y'):
        return dt.strftime(fmt) if dt else '—'

    def money(v):
        try:
            return f'PKR {float(v):,.0f}'
        except (TypeError, ValueError):
            return '—'

    DARK, MUTED, BORDER = TEXT_COLOR, MUTED_TEXT, BORDER_GREY
    styles = getSampleStyleSheet()
    st_sec = ParagraphStyle('sec', parent=styles['Normal'], fontSize=8.5, leading=12,
                            textColor=PRIMARY_COLOR, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=4)
    st_lbl = ParagraphStyle('l', parent=styles['Normal'], fontSize=7.5, leading=9, textColor=MUTED)
    st_val = ParagraphStyle('v', parent=styles['Normal'], fontSize=9, leading=12,
                            textColor=DARK, fontName='Helvetica-Bold')
    st_cell = ParagraphStyle('c', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=DARK)
    st_cell_muted = ParagraphStyle('cm', parent=styles['Normal'], fontSize=8, leading=11, textColor=MUTED)
    st_danger = ParagraphStyle('dg', parent=styles['Normal'], fontSize=9, leading=12,
                               textColor=PRIMARY_COLOR, fontName='Helvetica-Bold')
    st_th = ParagraphStyle('th', parent=styles['Normal'], fontSize=7.5, leading=10,
                           textColor=WHITE, fontName='Helvetica-Bold')
    CONTENT_W = A4[0] - 72

    buf = io.BytesIO()
    gen = ProfessionalPDFGenerator(buf, company, invoice_settings)
    gen.footer_message = 'Sales Recovery — Group Summary'
    elements = []

    elements.append(gen._build_header(
        'Recovery', doc_number=(customer.name or 'Group'),
        date=None, due_date=None, currency='PKR',
        status=f'{len(tasks)} open invoices',
    ))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width='100%', thickness=0.6, color=BORDER, spaceAfter=8))

    # Combined totals
    elements.append(Paragraph('Combined Totals', st_sec))
    trow = [[Paragraph('Total Invoice', st_lbl), Paragraph('Paid', st_lbl),
             Paragraph('Balance', st_lbl), Paragraph('Overdue', st_lbl), Paragraph('Invoices', st_lbl)],
            [Paragraph(money(total), st_val), Paragraph(money(paid), st_val),
             Paragraph(money(balance), st_danger), Paragraph(money(overdue_amount), st_danger),
             Paragraph(str(len(tasks)), st_val)]]
    tt = Table(trow, colWidths=[CONTENT_W * 0.22, CONTENT_W * 0.2, CONTENT_W * 0.2,
                                CONTENT_W * 0.2, CONTENT_W * 0.18])
    tt.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER), ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(tt)

    # Customer details
    elements.append(Paragraph('Customer Details', st_sec))
    elements.append(Table([
        [Paragraph('Company', st_lbl), Paragraph(customer.company_name or customer.name or '—', st_val)],
        [Paragraph('Phone', st_lbl), Paragraph(customer.phone or '—', st_cell)],
        [Paragraph('Email', st_lbl), Paragraph(customer.email or '—', st_cell)],
    ], colWidths=[CONTENT_W * 0.2, CONTENT_W * 0.8], style=TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER), ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])))

    # Invoices in group
    elements.append(Paragraph('Invoices in Group', st_sec))
    rows = [[Paragraph('Invoice #', st_th), Paragraph('Total', st_th), Paragraph('Paid', st_th),
             Paragraph('Balance', st_th), Paragraph('Status', st_th), Paragraph('Risk', st_th)]]
    for t in tasks:
        i = t.invoice
        rows.append([
            Paragraph(i.invoice_number if i else '—', st_cell),
            Paragraph(money(i.total) if i else '—', st_cell),
            Paragraph(money(i.paid_amount) if i else '—', st_cell),
            Paragraph(money(i.balance_due) if i else '—', st_danger),
            Paragraph((t.recovery_status or '').replace('_', ' ').title(), st_cell),
            Paragraph((t.risk_level or '—').title(), st_cell),
        ])
    rows.append([Paragraph('Total', st_th), Paragraph(money(total), st_th), Paragraph(money(paid), st_th),
                 Paragraph(money(balance), st_th), Paragraph('', st_th), Paragraph('', st_th)])
    it = Table(rows, repeatRows=1, colWidths=[CONTENT_W * 0.2, CONTENT_W * 0.18, CONTENT_W * 0.18,
                                              CONTENT_W * 0.18, CONTENT_W * 0.16, CONTENT_W * 0.1])
    it.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_STRIPE),
        ('BACKGROUND', (0, -1), (-1, -1), HEADER_STRIPE),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER), ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#fbfbfb')]),
    ]))
    elements.append(it)

    # Combined activity log
    elements.append(Paragraph('Activity Log', st_sec))
    logs = sorted((log for t in tasks for log in t.logs),
                  key=lambda l: l.created_at or datetime.min, reverse=True)
    if logs:
        rows = [[Paragraph('Date & Time', st_th), Paragraph('Invoice', st_th), Paragraph('Type', st_th),
                 Paragraph('By', st_th), Paragraph('Note', st_th)]]
        for log in logs:
            note = log.note or ''
            if log.promised_amount or log.promise_date:
                extra = []
                if log.promised_amount:
                    extra.append(money(log.promised_amount))
                if log.promise_date:
                    extra.append('by ' + d(log.promise_date))
                note += f"  ({' '.join(extra)})"
            rows.append([
                Paragraph(d(log.created_at, '%d-%m-%Y %H:%M'), st_cell_muted),
                Paragraph(log.task.invoice.invoice_number if log.task and log.task.invoice else '—', st_cell_muted),
                Paragraph((log.response_type or 'general').replace('_', ' ').title(), st_cell),
                Paragraph(log.logged_by_user.username if log.logged_by_user else '—', st_cell_muted),
                Paragraph(note, st_cell),
            ])
        lt = Table(rows, repeatRows=1, colWidths=[CONTENT_W * 0.16, CONTENT_W * 0.14, CONTENT_W * 0.14,
                                                  CONTENT_W * 0.12, CONTENT_W * 0.44])
        lt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_STRIPE),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER), ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fbfbfb')]),
        ]))
        elements.append(lt)
    else:
        elements.append(Paragraph('No activity logged yet.', st_cell_muted))

    # Bank details box (same as the invoice)
    if invoice_settings:
        payment_info = {k: v for k, v in {
            'Payment Terms':  getattr(invoice_settings, 'payment_terms', None),
            'Bank Name':      getattr(invoice_settings, 'bank_name', None),
            'Account Holder': getattr(invoice_settings, 'account_holder_name', None),
            'Account Number': getattr(invoice_settings, 'account_number', None),
            'IBAN':           getattr(invoice_settings, 'ifsc_code', None),
            'SWIFT Code':     getattr(invoice_settings, 'swift_code', None),
        }.items() if v}
    elif company:
        payment_info = {k: v for k, v in {
            'Bank Name':      getattr(company, 'bank_name', None),
            'Account Number': getattr(company, 'account_number', None),
            'IBAN':           getattr(company, 'ifsc_code', None),
        }.items() if v}
    else:
        payment_info = {}
    if payment_info:
        elements.append(Spacer(1, 12))
        bank_rows = [Paragraph('BANK DETAILS', gen.styles['NotesTitle'])]
        for k, v in payment_info.items():
            bank_rows.append(Paragraph(f'<b>{k}:</b> {v}', gen.styles['NotesText']))
        bank_tbl = Table([[item] for item in bank_rows], colWidths=[3.7 * inch])
        bank_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER), ('BACKGROUND', (0, 0), (-1, -1), WHITE),
        ]))
        bank_tbl.hAlign = 'LEFT'
        elements.append(bank_tbl)

    gen.doc.title = f'Recovery Group {customer.name or customer_id}'
    gen.doc.build(elements, onFirstPage=gen._draw_page_decorations,
                  onLaterPages=gen._draw_page_decorations)
    buf.seek(0)
    fname = f"Recovery_Group_{(customer.name or customer_id)}.pdf".replace(' ', '_')
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=fname)


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


# ─── Log a call / WhatsApp contact attempt (AJAX) ──────────────────────────────

@bp.route('/task/<int:task_id>/log-contact', methods=['POST'])
@login_required
def log_contact(task_id):
    """Record that the user initiated a phone call or WhatsApp contact from the
    detail page, so the attempt shows up in the Conversation Log. Called via
    fetch() just before the browser opens the tel:/WhatsApp link."""
    guard = _require_recovery_view()
    if guard:
        return jsonify({'ok': False, 'error': 'forbidden'}), 403

    task = RecoveryTask.query.get_or_404(task_id)
    method = request.form.get('method', '')
    name = (request.form.get('name', '') or '').strip()
    number = (request.form.get('number', '') or '').strip()

    if method not in ('call', 'whatsapp') or not number:
        return jsonify({'ok': False, 'error': 'bad_request'}), 400

    verb = 'Called' if method == 'call' else 'WhatsApp message/call to'
    who = f'{name} ({number})' if name else number
    note = f'{verb} {who}.'

    log = RecoveryLog(
        task_id=task.id,
        response_type='general',
        note=note,
        logged_by=current_user.id,
    )
    db.session.add(log)
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True, 'note': note})


# ─── Download the recovery detail page (with activity log) as a PDF ────────────

@bp.route('/task/<int:task_id>/pdf')
@login_required
def task_pdf(task_id):
    """A clean, printable PDF of the whole recovery detail: customer contacts,
    invoice + recovery status, broken-promise history and the full activity log."""
    guard = _require_recovery_view()
    if guard:
        return guard

    import io
    from flask import send_file
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from app.models import Company, InvoiceSettings
    # Reuse the exact Sales-invoice PDF engine so the recovery report shares the
    # same chrome: logo + company-address header, BANK DETAILS box and the
    # authorized-signature footer.
    from app.pdf_utils import (
        ProfessionalPDFGenerator, PRIMARY_COLOR, TEXT_COLOR, MUTED_TEXT,
        BORDER_GREY, HEADER_STRIPE, WHITE,
    )

    task = RecoveryTask.query.get_or_404(task_id)
    inv = task.invoice
    cust = inv.customer if inv else None
    company = Company.query.first()
    invoice_settings = InvoiceSettings.query.first()

    def d(dt, fmt='%d-%m-%Y'):
        return dt.strftime(fmt) if dt else '—'

    def money(v):
        try:
            return f'PKR {float(v):,.0f}'
        except (TypeError, ValueError):
            return '—'

    # ── Styles — matched to the Sales invoice palette ──────────────────────
    PRIMARY = PRIMARY_COLOR
    DARK = TEXT_COLOR
    MUTED = MUTED_TEXT
    DANGER = PRIMARY_COLOR
    LIGHT = colors.HexColor('#f2f2f2')
    BORDER = BORDER_GREY

    styles = getSampleStyleSheet()
    st_sec = ParagraphStyle('sec', parent=styles['Normal'], fontSize=8.5, leading=12,
                            textColor=PRIMARY, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=4)
    st_lbl = ParagraphStyle('l', parent=styles['Normal'], fontSize=7.5, leading=9, textColor=MUTED)
    st_val = ParagraphStyle('v', parent=styles['Normal'], fontSize=9, leading=12,
                            textColor=DARK, fontName='Helvetica-Bold')
    st_cell = ParagraphStyle('c', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=DARK)
    st_cell_muted = ParagraphStyle('cm', parent=styles['Normal'], fontSize=8, leading=11, textColor=MUTED)
    st_danger = ParagraphStyle('dg', parent=styles['Normal'], fontSize=9, leading=12,
                               textColor=DANGER, fontName='Helvetica-Bold')
    st_th = ParagraphStyle('th', parent=styles['Normal'], fontSize=7.5, leading=10,
                           textColor=WHITE, fontName='Helvetica-Bold')

    CONTENT_W = A4[0] - 72  # 36pt margins each side

    def kv_grid(pairs, cols=3, val_style=st_val):
        """Render label/value pairs in a bordered grid of `cols` columns."""
        cells = []
        for label, value, vstyle in pairs:
            cells.append([Paragraph(label.upper(), st_lbl),
                          Paragraph(str(value), vstyle or val_style)])
        rows, row = [], []
        for c in cells:
            inner = Table([[c[0]], [c[1]]], colWidths=[CONTENT_W / cols - 6])
            inner.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            row.append(inner)
            if len(row) == cols:
                rows.append(row); row = []
        if row:
            while len(row) < cols:
                row.append('')
            rows.append(row)
        t = Table(rows, colWidths=[CONTENT_W / cols] * cols)
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        return t

    # ── Build the invoice-styled document generator ────────────────────────
    buf = io.BytesIO()
    gen = ProfessionalPDFGenerator(buf, company, invoice_settings)
    gen.footer_message = 'Sales Recovery — Payment Follow-up'

    elements = []

    # ── Header — identical to the Sales invoice (logo + company address block,
    #    with the invoice number / dates on the right and a recovery-status badge).
    status_txt = task.recovery_status.replace('_', ' ').title()
    elements.append(gen._build_header(
        'Recovery',   # single word — keeps the 26pt title on one line (no wrap/overlap)
        doc_number=(inv.invoice_number if inv else task.id),
        date=(inv.date if inv else None),
        due_date=(inv.due_date if inv else None),
        currency='PKR',
        status=status_txt,
    ))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width='100%', thickness=0.6, color=BORDER, spaceAfter=8))

    # ── Customer details ───────────────────────────────────────────────────
    if cust:
        elements.append(Paragraph('Customer Details', st_sec))
        elements.append(kv_grid([
            ('Company Name', cust.company_name or cust.name, st_val),
            ('Primary Phone', cust.phone or '—', st_val),
            ('Email', cust.email or '—', st_cell),
        ], cols=3))

        # All names & numbers
        contacts = []
        if cust.phone:
            contacts.append((cust.company_name or cust.name, cust.phone))
        for sub in cust.sub_customers_list:
            if sub.get('name') or sub.get('phone'):
                contacts.append((sub.get('name', '—'), sub.get('phone', '—')))
        if contacts:
            elements.append(Spacer(1, 4))
            rows = [[Paragraph('Customer Name', st_th), Paragraph('Phone Number', st_th)]]
            for name, phone in contacts:
                rows.append([Paragraph(str(name or '—'), st_cell),
                             Paragraph(str(phone or '—'), st_cell)])
            ct = Table(rows, colWidths=[CONTENT_W * 0.6, CONTENT_W * 0.4])
            ct.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HEADER_STRIPE),
                ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
                ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(ct)

    # ── Invoice & recovery status ──────────────────────────────────────────
    elements.append(Paragraph('Invoice & Recovery Status', st_sec))
    status_txt = task.recovery_status.replace('_', ' ').title()
    elements.append(kv_grid([
        ('Total Invoice', money(inv.total) if inv else '—', st_val),
        ('Paid', money(inv.paid_amount) if inv else '—', st_val),
        ('Balance', money(inv.balance_due) if inv else '—', st_danger),
        ('Invoice Date', d(inv.date) if inv else '—', st_cell),
        ('Due Date', d(inv.due_date) if inv else '—', st_cell),
        ('Overdue Days', f'{task.overdue_days} days', st_danger if task.overdue_days > 0 else st_val),
        ('Recovery Status', status_txt, st_val),
        ('Risk Level', (task.risk_level or '—').title(), st_val),
        ('Salesman', (task.salesman.name if task.salesman else (inv.salesman.name if inv and inv.salesman else '—')), st_cell),
    ], cols=3))

    # ── Promise / broken-promise summary ───────────────────────────────────
    elements.append(Paragraph('Payment Promise', st_sec))
    elements.append(kv_grid([
        ('Promise Date', d(task.promise_date), st_val),
        ('Promised Amount', money(task.promised_amount) if task.promised_amount else '—', st_val),
        ('Broken Promises', str(task.broken_promise_count or 0),
         st_danger if task.broken_promise_count else st_val),
    ], cols=3))

    broken = task.broken_promises
    if broken:
        elements.append(Spacer(1, 4))
        rows = [[Paragraph('Promised By', st_th), Paragraph('Amount', st_th),
                 Paragraph('Broken On', st_th)]]
        for bp in broken:
            rows.append([
                Paragraph(d(bp['date']), st_cell),
                Paragraph(money(bp['amount']) if bp['amount'] else '—', st_danger),
                Paragraph(d(bp['when']), st_cell_muted),
            ])
        bt = Table(rows, colWidths=[CONTENT_W * 0.35, CONTENT_W * 0.35, CONTENT_W * 0.30])
        bt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_STRIPE),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(bt)

    # ── Other open invoices for the same customer ──────────────────────────
    sibling_tasks = []
    if inv and inv.customer_id:
        sibling_tasks = [t for t in open_tasks_for_customer(inv.customer_id) if t.id != task.id]
    if sibling_tasks:
        elements.append(Paragraph(f'Other Open Invoices ({len(sibling_tasks)})', st_sec))
        rows = [[Paragraph('Invoice #', st_th), Paragraph('Balance', st_th),
                 Paragraph('Recovery Status', st_th), Paragraph('Promise Date', st_th),
                 Paragraph('Risk', st_th)]]
        for st_ in sibling_tasks:
            sinv = st_.invoice
            rows.append([
                Paragraph(sinv.invoice_number if sinv else '—', st_cell),
                Paragraph(money(sinv.balance_due) if sinv else '—', st_danger),
                Paragraph((st_.recovery_status or '').replace('_', ' ').title(), st_cell),
                Paragraph(d(st_.promise_date), st_cell),
                Paragraph((st_.risk_level or '—').title(), st_cell),
            ])
        ot = Table(rows, repeatRows=1,
                   colWidths=[CONTENT_W * 0.18, CONTENT_W * 0.18, CONTENT_W * 0.30,
                              CONTENT_W * 0.18, CONTENT_W * 0.16])
        ot.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_STRIPE),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fbfbfb')]),
        ]))
        elements.append(ot)

    # ── Activity / Conversation log ────────────────────────────────────────
    elements.append(Paragraph('Activity Log', st_sec))
    if task.logs:
        rows = [[Paragraph('Date & Time', st_th), Paragraph('Type', st_th),
                 Paragraph('By', st_th), Paragraph('Note', st_th)]]
        for log in task.logs:  # newest first
            note = log.note or ''
            if log.promised_amount or log.promise_date:
                extra = []
                if log.promised_amount:
                    extra.append(money(log.promised_amount))
                if log.promise_date:
                    extra.append('by ' + d(log.promise_date))
                note += f"  ({' '.join(extra)})"
            rows.append([
                Paragraph(d(log.created_at, '%d-%m-%Y %H:%M'), st_cell_muted),
                Paragraph((log.response_type or 'general').replace('_', ' ').title(), st_cell),
                Paragraph(log.logged_by_user.username if log.logged_by_user else '—', st_cell_muted),
                Paragraph(note, st_cell),
            ])
        lt = Table(rows, repeatRows=1,
                   colWidths=[CONTENT_W * 0.18, CONTENT_W * 0.16, CONTENT_W * 0.14, CONTENT_W * 0.52])
        lt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_STRIPE),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fbfbfb')]),
        ]))
        elements.append(lt)
    else:
        elements.append(Paragraph('No activity logged yet.', st_cell_muted))

    # ── Bank / payment details box — same fields & styling as the invoice ──
    if invoice_settings:
        payment_info = {k: v for k, v in {
            'Payment Terms':  getattr(invoice_settings, 'payment_terms', None),
            'Bank Name':      getattr(invoice_settings, 'bank_name', None),
            'Account Holder': getattr(invoice_settings, 'account_holder_name', None),
            'Account Number': getattr(invoice_settings, 'account_number', None),
            'IBAN':           getattr(invoice_settings, 'ifsc_code', None),
            'SWIFT Code':     getattr(invoice_settings, 'swift_code', None),
        }.items() if v}
    elif company:
        payment_info = {k: v for k, v in {
            'Bank Name':      getattr(company, 'bank_name', None),
            'Account Number': getattr(company, 'account_number', None),
            'IBAN':           getattr(company, 'ifsc_code', None),
        }.items() if v}
    else:
        payment_info = {}

    if payment_info:
        elements.append(Spacer(1, 12))
        bank_rows = [Paragraph('BANK DETAILS', gen.styles['NotesTitle'])]
        for k, v in payment_info.items():
            bank_rows.append(Paragraph(f'<b>{k}:</b> {v}', gen.styles['NotesText']))
        bank_tbl = Table([[item] for item in bank_rows], colWidths=[3.7 * inch])
        bank_tbl.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('ALIGN',         (0, 0), (-1, -1), 'LEFT'),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
            ('BOX',           (0, 0), (-1, -1), 0.5, BORDER),
            ('BACKGROUND',    (0, 0), (-1, -1), WHITE),
        ]))
        bank_tbl.hAlign = 'LEFT'   # align with the tables above, not centered
        elements.append(bank_tbl)

    # ── Build — reuse the invoice page decorations (grey page, white card,
    #    top stripe) and the authorized-signature footer. ───────────────────
    gen.doc.title = f'Recovery {inv.invoice_number if inv else task.id}'
    gen.doc.build(elements,
                  onFirstPage=gen._draw_page_decorations,
                  onLaterPages=gen._draw_page_decorations)
    buf.seek(0)
    fname = f"Recovery_{(inv.invoice_number if inv else task.id)}.pdf".replace(' ', '_')
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=fname)


# ─── Comments (plain discussion thread, no automation impact) ──────────────────

@bp.route('/task/<int:task_id>/add-comment', methods=['POST'])
@login_required
def add_comment(task_id):
    if not (current_user.is_admin or current_user.can_add_recovery):
        flash('Permission denied.', 'danger')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    task = RecoveryTask.query.get_or_404(task_id)
    text = request.form.get('comment', '').strip()

    if not text:
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    db.session.add(RecoveryComment(
        task_id=task.id,
        comment=text,
        created_by=current_user.id,
    ))
    db.session.commit()

    flash('Comment added.', 'success')
    return redirect(url_for('recovery.task_detail', task_id=task_id))


@bp.route('/comment/<int:comment_id>/edit', methods=['POST'])
@login_required
def edit_comment(comment_id):
    """Edit an existing comment. Admin-only — regular staff can add comments
    but only an admin may change one after it was posted."""
    comment = RecoveryComment.query.get_or_404(comment_id)

    if not current_user.is_admin:
        flash('Only an admin can edit comments.', 'danger')
        return redirect(url_for('recovery.task_detail', task_id=comment.task_id))

    text = request.form.get('comment', '').strip()
    if not text:
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('recovery.task_detail', task_id=comment.task_id))

    comment.comment = text
    comment.edited_at = datetime.utcnow()
    db.session.commit()

    flash('Comment updated.', 'success')
    return redirect(url_for('recovery.task_detail', task_id=comment.task_id))


@bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    """Delete a comment. Admin-only — same policy as editing."""
    comment = RecoveryComment.query.get_or_404(comment_id)

    if not current_user.is_admin:
        flash('Only an admin can delete comments.', 'danger')
        return redirect(url_for('recovery.task_detail', task_id=comment.task_id))

    task_id = comment.task_id
    db.session.delete(comment)
    db.session.commit()

    flash('Comment deleted.', 'success')
    return redirect(url_for('recovery.task_detail', task_id=task_id))


@bp.route('/log/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_log(log_id):
    """Delete a Conversation Log entry. Admin-only — same policy as comments."""
    log = RecoveryLog.query.get_or_404(log_id)

    if not current_user.is_admin:
        flash('Only an admin can delete conversation log messages.', 'danger')
        return redirect(url_for('recovery.task_detail', task_id=log.task_id))

    task_id = log.task_id
    db.session.delete(log)
    db.session.commit()

    flash('Conversation log message deleted.', 'success')
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


# ─── Mark Promise for a whole customer (all their open invoices at once) ──────

@bp.route('/customer/<int:customer_id>/mark-promise', methods=['POST'])
@login_required
def mark_promise_customer(customer_id):
    # Lets this be triggered from either the dashboard's customer row or a
    # single invoice's Task Detail page — sends staff back to wherever they
    # started instead of always bouncing to the dashboard.
    redirect_task_id = request.form.get('redirect_task_id', '').strip()
    fallback = (redirect(url_for('recovery.task_detail', task_id=redirect_task_id))
                if redirect_task_id else redirect(url_for('recovery.dashboard')))

    if not (current_user.is_admin or current_user.can_add_recovery):
        flash('Permission denied.', 'danger')
        return fallback

    tasks = open_tasks_for_customer(customer_id)
    if not tasks:
        flash('No open recovery invoices for this customer.', 'warning')
        return fallback

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
        return fallback

    promise_date = promise_dt.date()

    for t in tasks:
        t.recovery_status = 'PROMISED_PAYMENT'
        t.promise_date = promise_date
        t.promised_amount = promised_amount
        t.next_follow_up_date = promise_date
        t.updated_at = datetime.utcnow()
        db.session.add(RecoveryLog(
            task_id=t.id,
            response_type='promised_payment',
            note=note or f'Customer-wide promise: PKR {promised_amount:,.0f} by {promise_dt.strftime("%d-%m-%Y %H:%M")} (covers all open invoices).',
            promised_amount=promised_amount,
            promise_date=promise_date,
            next_follow_up_date=promise_date,
            logged_by=current_user.id,
        ))

    # Clear every existing popup for this customer's invoices first, so leftover
    # per-invoice reminders can't all fire at once at promise time. Then re-arm
    # exactly ONE consolidated reminder per salesman the invoices belong to.
    # Muted / on-hold invoices are excluded from the reminder group entirely.
    cancel_group_reminders(tasks)
    by_salesman = {}
    for t in tasks:
        if t.is_muted or t.is_on_hold:
            continue
        by_salesman.setdefault(t.salesman_id, []).append(t)
    for salesman_tasks in by_salesman.values():
        rearm_group_reminder(salesman_tasks, promise_dt)

    db.session.commit()

    flash(f'Promise recorded for {len(tasks)} invoice(s). One consolidated reminder will pop up at the promised time.', 'success')
    return fallback


# ─── Mute / Unmute Notifications ───────────────────────────────────────────────

@bp.route('/task/<int:task_id>/toggle-mute', methods=['POST'])
@login_required
def toggle_mute(task_id):
    """Per-invoice checkbox: pause (or resume) popup reminders + the dashboard
    countdown for one invoice's recovery task, without touching its
    recovery_status. Does not affect sibling invoices in the same
    customer+salesman group."""
    if not (current_user.is_admin or current_user.can_edit_recovery):
        return jsonify({'success': False, 'message': 'Permission denied.'}), 403

    task = RecoveryTask.query.get_or_404(task_id)
    task.is_muted = not task.is_muted
    task.updated_at = datetime.utcnow()

    if task.is_muted:
        task.muted_at = datetime.utcnow()
        task.muted_by = current_user.id

        # The group's current popup (if any) may reference this invoice in its
        # title/description/balance — cancel it and, if other non-muted
        # invoices remain in the group, raise a fresh one that no longer
        # mentions this one.
        if task.invoice and task.invoice.customer_id:
            group = open_tasks_for_group(task.invoice.customer_id, task.salesman_id)
            cancel_group_reminders(group)
            siblings = [t for t in group if t.id != task.id and not t.is_muted]
            if siblings:
                rearm_group_reminder(siblings, pk_now())

        db.session.add(RecoveryLog(
            task_id=task.id, response_type='general',
            note=f'Notifications muted by {current_user.username}.',
            logged_by=current_user.id,
        ))
    else:
        task.muted_at = None
        task.muted_by = None
        db.session.add(RecoveryLog(
            task_id=task.id, response_type='general',
            note=f'Notifications unmuted by {current_user.username}.',
            logged_by=current_user.id,
        ))
        # Let it rejoin the group's reminder (or get its own) right away
        # instead of waiting for the next automation cycle.
        from app.services.recovery_automation import _ensure_reminder
        if task.recovery_status not in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF'):
            _ensure_reminder(task)

    db.session.commit()
    return jsonify({'success': True, 'is_muted': task.is_muted})


# ─── Put On Hold / Resume ──────────────────────────────────────────────────────

@bp.route('/task/<int:task_id>/toggle-hold', methods=['POST'])
@login_required
def toggle_hold(task_id):
    """Mark this invoice's recovery task 'On Hold' (or take it off hold). While
    on hold it behaves like a mute — no popup reminders are raised and the
    countdown timer does not run — but it is also flagged with a visible
    'On Hold' status and collected under the dashboard's On Hold tab, so staff
    know it is intentionally parked rather than merely silenced.

    Supports two callers: the Task Detail button (a plain form POST → redirects
    back with a flash) and the dashboard row (posts ajax=1 → JSON response)."""
    wants_json = request.form.get('ajax') == '1'

    def _fail(msg, code=403):
        if wants_json:
            return jsonify({'success': False, 'message': msg}), code
        flash(msg, 'danger')
        return redirect(url_for('recovery.task_detail', task_id=task_id))

    if not (current_user.is_admin or current_user.can_edit_recovery):
        return _fail('Permission denied.')

    task = RecoveryTask.query.get_or_404(task_id)
    task.is_on_hold = not task.is_on_hold
    task.updated_at = datetime.utcnow()

    if task.is_on_hold:
        task.on_hold_at = datetime.utcnow()
        task.on_hold_by = current_user.id

        # Drop the group's current popup (it may reference this invoice) and, if
        # other still-active invoices remain in the group, raise a fresh one so
        # they keep getting reminders without this held one.
        if task.invoice and task.invoice.customer_id:
            group = open_tasks_for_group(task.invoice.customer_id, task.salesman_id)
            cancel_group_reminders(group)
            siblings = [t for t in group
                        if t.id != task.id and not t.is_muted and not t.is_on_hold]
            if siblings:
                rearm_group_reminder(siblings, pk_now())

        db.session.add(RecoveryLog(
            task_id=task.id, response_type='general',
            note=f'Invoice put On Hold by {current_user.username}.',
            logged_by=current_user.id,
        ))
    else:
        task.on_hold_at = None
        task.on_hold_by = None
        db.session.add(RecoveryLog(
            task_id=task.id, response_type='general',
            note=f'Invoice taken off hold by {current_user.username}.',
            logged_by=current_user.id,
        ))
        # Let it rejoin the group's reminder right away rather than waiting for
        # the next automation cycle.
        from app.services.recovery_automation import _ensure_reminder
        if not task.is_muted and task.recovery_status not in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF'):
            _ensure_reminder(task)

    db.session.commit()

    if wants_json:
        return jsonify({'success': True, 'is_on_hold': task.is_on_hold})
    flash('Invoice put on hold.' if task.is_on_hold else 'Invoice taken off hold.', 'success')
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


# ─── Recovery Reminder Broadcasts (admins: site-wide; salesmen: own only) ─────

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
    return pk_now()


def _still_in_recovery(t):
    """True only if the popup reminder's linked recovery task is still a live
    item in the Recovery module. An invoice leaves the module when it is
    drafted, cancelled, or fully paid in Sales, or when its recovery task is
    closed. Broadcasts ("could not call…", "task complete…") must never fire
    for invoices that are no longer in Recovery — that was the source of the
    stale/duplicate escalation notices."""
    rtask = t.recovery_task
    if not rtask:
        return False
    if rtask.recovery_status in ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF'):
        return False
    inv = rtask.invoice
    if not inv:
        return False
    # Draft or cancelled in Sales.
    if inv.is_draft:
        return False
    if inv.is_rejected and inv.rejection_reason == CANCELLED_REASON:
        return False
    # Fully paid in Sales — nothing left to recover.
    if inv.status == 'paid' or (inv.balance_due or 0) <= 0:
        return False
    return True


@bp.route('/broadcasts/poll')
@login_required
def poll_broadcasts():
    # Admins see every salesman's broadcasts (oversight). A non-admin only
    # sees broadcasts for the salesman(s) their own login is linked to in the
    # Salesman module — never anyone else's.
    if current_user.is_admin:
        my_salesman_ids = None
    else:
        my_salesman_ids = {s.id for s in current_user.linked_salesmen}
        if not my_salesman_ids:
            return jsonify([])

    def _visible(t):
        return my_salesman_ids is None or (t.recovery_task and t.recovery_task.salesman_id in my_salesman_ids)

    now = _parse_client_time()
    messages = []
    changed = False

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
        # Invoice left the Recovery module (draft/cancelled/fully paid/closed):
        # retire the pending broadcast so it never surfaces and stops being
        # re-evaluated on every poll.
        if not _still_in_recovery(t):
            t.is_escalation_broadcast_shown = True
            changed = True
            continue
        if not _visible(t):
            continue
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
        if not _still_in_recovery(t):
            t.is_completion_broadcast_shown = True
            changed = True
            continue
        if not _visible(t):
            continue
        inv = t.recovery_task.invoice if t.recovery_task else None
        customer_name = inv.customer.name if inv and inv.customer else 'the customer'
        messages.append({
            'id': t.id,
            'kind': 'completion',
            'text': f'Task complete: {t.assigned_to.username} called this {customer_name}.'
        })

    if changed:
        db.session.commit()

    return jsonify(messages)


@bp.route('/broadcasts/dismiss/<int:task_id>', methods=['POST'])
@login_required
def dismiss_broadcast(task_id):
    task = Task.query.get_or_404(task_id)

    if not current_user.is_admin:
        my_salesman_ids = {s.id for s in current_user.linked_salesmen}
        if not task.recovery_task or task.recovery_task.salesman_id not in my_salesman_ids:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403

    kind = request.form.get('kind')

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
    return pk_now()


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

    invoice = rtask.invoice
    if invoice and invoice.customer_id:
        group_tasks = open_tasks_for_group(invoice.customer_id, rtask.salesman_id) or [rtask]
    else:
        group_tasks = [rtask]

    for t in group_tasks:
        t.recovery_status = 'PROMISED_PAYMENT'
        t.promise_date = promise_date
        t.promised_amount = promised_amount
        t.next_follow_up_date = promise_date
        t.updated_at = datetime.utcnow()
        db.session.add(RecoveryLog(
            task_id=t.id,
            response_type='promised_payment',
            note=f'{current_user.username} recorded a promise: PKR {promised_amount:,.0f} by {promise_dt.strftime("%d-%m-%Y %H:%M")}.',
            promised_amount=promised_amount,
            promise_date=promise_date,
            next_follow_up_date=promise_date,
            logged_by=current_user.id,
        ))

    # Re-arm this reminder to fire again at the exact promised date/time.
    reminder.reminder_at = promise_dt
    reminder.is_notification_shown = False
    reminder.is_email_sent = False

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

_RISK_RANK = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}


def _dedupe_by_invoice(tasks):
    """Collapse duplicate RecoveryTask rows that point at the same invoice so
    each invoice appears (and is counted) exactly once. Preserves input order,
    keeping the first occurrence — callers pass an already-prioritised list.
    Tasks with no invoice are always kept (keyed by their own id)."""
    seen = set()
    out = []
    for t in tasks:
        key = ('inv', t.invoice_id) if t.invoice_id else ('task', t.id)
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _group_tasks_by_customer(tasks):
    """Fold a flat, already-sorted (risk desc, updated_at desc) list of
    RecoveryTasks into one row per customer with aggregated totals, so a
    customer with several overdue invoices shows as a single expandable row
    instead of one row per invoice. Group order follows the first (most
    urgent/recent) task encountered for each customer."""
    groups = {}
    order = []
    for t in tasks:
        inv = t.invoice
        cust = inv.customer if inv else None
        key = cust.id if cust else 0
        if key not in groups:
            groups[key] = {'customer': cust, 'tasks': []}
            order.append(key)
        groups[key]['tasks'].append(t)

    customer_groups = []
    for key in order:
        g = groups[key]
        gtasks = g['tasks']
        invs = [t.invoice for t in gtasks if t.invoice]
        promise_dates = [t.promise_date for t in gtasks if t.promise_date]
        reminder_times = [t.next_reminder_at for t in gtasks if t.next_reminder_at]
        customer_groups.append({
            'customer': g['customer'],
            'tasks': gtasks,
            'invoice_count': len(gtasks),
            'total': sum(i.total for i in invs),
            'paid': sum(i.paid_amount for i in invs),
            'balance': sum(i.balance_due for i in invs),
            'overdue_amount': sum(i.overdue_amount for i in invs),
            'worst_risk': max((t.risk_level for t in gtasks), key=lambda r: _RISK_RANK.get(r, 0), default='low'),
            'any_escalated': any(t.is_escalated for t in gtasks),
            'earliest_promise': min(promise_dates) if promise_dates else None,
            'soonest_reminder': min(reminder_times) if reminder_times else None,
        })
    return customer_groups


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
    """Make the popup reminder for this recovery task's customer+salesman
    group fire at `when_dt` (one popup covers all of that customer's open
    invoices for this salesman)."""
    invoice = rtask.invoice
    if invoice and invoice.customer_id:
        group_tasks = open_tasks_for_group(invoice.customer_id, rtask.salesman_id)
    else:
        group_tasks = [rtask]
    return rearm_group_reminder(group_tasks or [rtask], when_dt)
