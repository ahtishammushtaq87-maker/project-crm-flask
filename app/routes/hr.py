"""HR module: Leave & Absence, Bonuses & Adjustments, Assets & Custody,
Final Settlements, Salary Revisions, and a Company Funds summary page.

Staff, Attendance, Payroll Runs and Advances & Loans are NOT here -- they
stay in app/routes/salary.py and app/routes/attendance.py (existing,
working modules, only restyled). This blueprint hosts the HR sub-modules
confirmed for full build-out, gated by the umbrella can_view_hr /
can_add_hr / can_edit_hr / can_delete_hr permissions on User.
"""
from datetime import datetime, timedelta
import os

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.utils import permission_required, log_activity
from app.models import (
    Staff, Attendance, ExpenseAccount, Company,
    LeaveType, LeaveRequest, SalaryAdjustment, Asset, AssetAssignment, AssetCategory, Settlement,
    SalaryRevision,
)
from app.forms import (
    LeaveTypeForm, LeaveRequestForm, SalaryAdjustmentForm,
    AssetForm, AssetAssignmentForm, SettlementInitiateForm, SalaryRevisionForm,
)

bp = Blueprint('hr', __name__, url_prefix='/hr')


def _active_staff_choices():
    return [(s.id, s.name) for s in Staff.query.filter_by(is_active=True).order_by(Staff.name).all()]


# ═══════════════════════════════════════════════════════════════════════
# Leave & Absence
# ═══════════════════════════════════════════════════════════════════════

def apply_leave_approval_to_attendance(leave_request):
    """Upsert one Attendance row per non-Sunday date in the leave request's
    range, crediting a full paid day. Returns a list of dates that were
    skipped because they're already marked as a holiday for that staff
    (converting those would shrink that month's holiday divisor and
    silently change every other day's pay -- see Staff.calculate_daily_salary,
    which only ever filters on is_holiday).

    Deliberately does NOT set earned_amount directly: it sets
    hours_worked=8 and calls the record's own calculate_hourly_rate() /
    calculate_earned_amount(), so a paid leave day flows through the exact
    same formula as a normal worked day (neither is_holiday nor is_absent
    is set, so it lands in the regular-hours branch and naturally computes
    8 * (daily_salary/8) == daily_salary).
    """
    staff = leave_request.staff
    skipped_holiday_dates = []
    day = leave_request.start_date
    one_day = timedelta(days=1)

    while day <= leave_request.end_date:
        if day.weekday() == 6:  # Sunday -- matches get_working_days_in_month's convention
            day += one_day
            continue

        existing = Attendance.query.filter_by(staff_id=staff.id, date=day).first()

        if existing:
            if existing.is_holiday:
                skipped_holiday_dates.append(day)
            elif existing.clock_in:
                # Real attendance already recorded for this date -- don't
                # touch hours/pay, just link it for traceability.
                existing.leave_request_id = leave_request.id
            else:
                # Blank / auto-absent placeholder row -> convert to paid leave.
                existing.is_absent = False
                existing.is_paid_leave = True
                existing.leave_request_id = leave_request.id
                existing.hours_worked = 8
                existing.minutes_worked = 0
                existing.calculate_hourly_rate()
                existing.calculate_earned_amount()
        else:
            att = Attendance(staff_id=staff.id, date=day)
            att.is_paid_leave = True
            att.leave_request_id = leave_request.id
            att.hours_worked = 8
            att.minutes_worked = 0
            db.session.add(att)
            db.session.flush()
            att.calculate_hourly_rate()
            att.calculate_earned_amount()

        day += one_day

    return skipped_holiday_dates


@bp.route('/leave')
@login_required
def leave_list():
    query = LeaveRequest.query
    staff_id = request.args.get('staff_id', type=int)
    status = request.args.get('status', '')
    if staff_id:
        query = query.filter(LeaveRequest.staff_id == staff_id)
    if status:
        query = query.filter(LeaveRequest.status == status)
    requests_ = query.order_by(LeaveRequest.created_at.desc()).all()

    today = datetime.utcnow().date()
    month_start = today.replace(day=1)
    pending_count = LeaveRequest.query.filter_by(status='pending').count()
    approved_this_month = LeaveRequest.query.filter(
        LeaveRequest.status == 'approved', LeaveRequest.approved_at >= month_start
    ).count()
    unplanned_absences = Attendance.query.filter(
        Attendance.is_absent == True, Attendance.date >= month_start
    ).count()

    return render_template(
        'hr/leave_list.html',
        requests=requests_, all_staff=_active_staff_choices(),
        selected_staff_id=staff_id, selected_status=status,
        pending_count=pending_count, approved_this_month=approved_this_month,
        unplanned_absences=unplanned_absences, hr_module='hr_leave',
    )


@bp.route('/leave/add', methods=['GET', 'POST'])
@login_required
@permission_required('hr', action='add')
def add_leave_request():
    form = LeaveRequestForm()
    form.staff_id.choices = _active_staff_choices()
    form.leave_type_id.choices = [(t.id, t.name) for t in LeaveType.query.filter_by(is_active=True).order_by(LeaveType.name).all()]

    if not form.leave_type_id.choices:
        flash('Add at least one Leave Type before submitting a leave request.', 'warning')
        return redirect(url_for('hr.leave_types_list'))

    if form.validate_on_submit():
        if form.end_date.data < form.start_date.data:
            flash('End date cannot be before start date.', 'danger')
            return render_template('hr/leave_form.html', form=form, title='Request Leave')

        days = sum(
            1 for i in range((form.end_date.data - form.start_date.data).days + 1)
            if (form.start_date.data + timedelta(days=i)).weekday() != 6
        )

        leave = LeaveRequest(
            staff_id=form.staff_id.data, leave_type_id=form.leave_type_id.data,
            start_date=form.start_date.data, end_date=form.end_date.data,
            days=days, reason=form.reason.data, created_by=current_user.id,
        )

        if form.evidence.data:
            file = form.evidence.data
            filename = secure_filename(f"leave_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            upload_folder = os.path.join('app', 'static', 'uploads', 'leave_evidence')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            file.save(os.path.join(upload_folder, filename))
            leave.evidence_path = f'uploads/leave_evidence/{filename}'

        db.session.add(leave)
        db.session.commit()
        log_activity('HR', f'Leave requested: {leave.staff.name}', f'{leave.start_date} to {leave.end_date} ({days} days)')
        flash('Leave request submitted.', 'success')
        return redirect(url_for('hr.leave_list'))

    return render_template('hr/leave_form.html', form=form, title='Request Leave')


@bp.route('/leave/<int:id>/approve', methods=['POST'])
@login_required
@permission_required('hr', action='edit')
def approve_leave_request(id):
    leave = LeaveRequest.query.get_or_404(id)
    if leave.status != 'pending':
        flash('This leave request has already been actioned.', 'warning')
        return redirect(url_for('hr.leave_list'))

    skipped = apply_leave_approval_to_attendance(leave)
    leave.status = 'approved'
    leave.approved_by = current_user.id
    leave.approved_at = datetime.utcnow()
    db.session.commit()

    log_activity('HR', f'Leave approved: {leave.staff.name}', f'{leave.start_date} to {leave.end_date}')
    if skipped:
        dates_str = ', '.join(d.strftime('%d-%b') for d in skipped)
        flash(
            f'Leave approved, but {dates_str} already marked as a company holiday for {leave.staff.name} '
            'was left untouched (converting it would change pay for every other day that month). '
            'Review manually if needed.', 'warning'
        )
    else:
        flash(f'Leave approved. {leave.staff.name} is now marked Present (paid) for the leave dates.', 'success')
    return redirect(url_for('hr.leave_list'))


@bp.route('/leave/<int:id>/reject', methods=['POST'])
@login_required
@permission_required('hr', action='edit')
def reject_leave_request(id):
    leave = LeaveRequest.query.get_or_404(id)
    if leave.status != 'pending':
        flash('This leave request has already been actioned.', 'warning')
        return redirect(url_for('hr.leave_list'))

    leave.status = 'rejected'
    leave.approved_by = current_user.id
    leave.approved_at = datetime.utcnow()
    leave.rejection_reason = request.form.get('rejection_reason', '')
    db.session.commit()
    log_activity('HR', f'Leave rejected: {leave.staff.name}', f'{leave.start_date} to {leave.end_date}')
    flash('Leave request rejected.', 'info')
    return redirect(url_for('hr.leave_list'))


@bp.route('/leave-types')
@login_required
def leave_types_list():
    types_ = LeaveType.query.order_by(LeaveType.name).all()
    return render_template('hr/leave_types.html', leave_types=types_, form=LeaveTypeForm(), hr_module='hr_leave')


@bp.route('/leave-types/add', methods=['POST'])
@login_required
@permission_required('hr', action='add')
def add_leave_type():
    form = LeaveTypeForm()
    if form.validate_on_submit():
        lt = LeaveType(
            name=form.name.data, is_paid=form.is_paid.data,
            default_annual_days=form.default_annual_days.data or 0,
            is_active=form.is_active.data,
        )
        db.session.add(lt)
        db.session.commit()
        log_activity('HR', f'Leave type added: {lt.name}', '')
        flash('Leave type added.', 'success')
    else:
        flash('Could not add leave type — check the form.', 'danger')
    return redirect(url_for('hr.leave_types_list'))


# ═══════════════════════════════════════════════════════════════════════
# Bonuses & Adjustments
# ═══════════════════════════════════════════════════════════════════════

@bp.route('/adjustments')
@login_required
def adjustment_list():
    query = SalaryAdjustment.query
    staff_id = request.args.get('staff_id', type=int)
    status = request.args.get('status', '')
    adj_type = request.args.get('type', '')
    if staff_id:
        query = query.filter(SalaryAdjustment.staff_id == staff_id)
    if status:
        query = query.filter(SalaryAdjustment.status == status)
    if adj_type:
        query = query.filter(SalaryAdjustment.adjustment_type == adj_type)
    adjustments = query.order_by(SalaryAdjustment.created_at.desc()).all()

    recurring_count = SalaryAdjustment.query.filter_by(is_recurring=True, adjustment_type='allowance', status='approved').count()
    one_time_bonus_total = sum(
        a.amount for a in SalaryAdjustment.query.filter_by(adjustment_type='bonus', is_recurring=False).all()
    )
    pending_deductions = SalaryAdjustment.query.filter_by(adjustment_type='deduction', status='pending').count()
    rejected_count = SalaryAdjustment.query.filter_by(status='rejected').count()

    return render_template(
        'hr/adjustment_list.html',
        adjustments=adjustments, all_staff=_active_staff_choices(),
        selected_staff_id=staff_id, selected_status=status, selected_type=adj_type,
        recurring_count=recurring_count, one_time_bonus_total=one_time_bonus_total,
        pending_deductions=pending_deductions, rejected_count=rejected_count,
        hr_module='hr_adjustments',
    )


@bp.route('/adjustments/add', methods=['GET', 'POST'])
@login_required
@permission_required('hr', action='add')
def add_adjustment():
    form = SalaryAdjustmentForm()
    form.staff_id.choices = _active_staff_choices()

    if form.validate_on_submit():
        adj = SalaryAdjustment(
            staff_id=form.staff_id.data,
            adjustment_type=form.adjustment_type.data,
            amount=form.amount.data,
            reason=form.reason.data,
            is_recurring=form.is_recurring.data,
            effective_from=form.effective_from.data,
            payroll_month=form.payroll_month.data or None,
            payroll_year=form.payroll_year.data or None,
            evidence_text=form.evidence_text.data,
            created_by=current_user.id,
            status='approved' if current_user.is_admin else 'pending',
        )
        if adj.status == 'approved':
            adj.approved_by = current_user.id
            adj.approved_at = datetime.utcnow()

        db.session.add(adj)
        db.session.commit()
        log_activity('HR', f'Adjustment added: {adj.staff.name} ({adj.adjustment_type})', f'PKR {adj.amount}')
        flash('Adjustment recorded.' + ('' if adj.status == 'approved' else ' Awaiting approval.'), 'success')
        return redirect(url_for('hr.adjustment_list'))

    return render_template('hr/adjustment_form.html', form=form, title='Add Bonus / Adjustment')


@bp.route('/adjustments/<int:id>/approve', methods=['POST'])
@login_required
@permission_required('hr', action='edit')
def approve_adjustment(id):
    adj = SalaryAdjustment.query.get_or_404(id)
    if adj.status != 'pending':
        flash('This adjustment has already been actioned.', 'warning')
        return redirect(url_for('hr.adjustment_list'))
    adj.status = 'approved'
    adj.approved_by = current_user.id
    adj.approved_at = datetime.utcnow()
    db.session.commit()
    log_activity('HR', f'Adjustment approved: {adj.staff.name}', f'PKR {adj.amount}')
    flash('Adjustment approved. It will be pre-filled next time payroll runs for this staff member.', 'success')
    return redirect(url_for('hr.adjustment_list'))


@bp.route('/adjustments/<int:id>/reject', methods=['POST'])
@login_required
@permission_required('hr', action='edit')
def reject_adjustment(id):
    adj = SalaryAdjustment.query.get_or_404(id)
    if adj.status != 'pending':
        flash('This adjustment has already been actioned.', 'warning')
        return redirect(url_for('hr.adjustment_list'))
    adj.status = 'rejected'
    adj.approved_by = current_user.id
    adj.approved_at = datetime.utcnow()
    db.session.commit()
    log_activity('HR', f'Adjustment rejected: {adj.staff.name}', f'PKR {adj.amount}')
    flash('Adjustment rejected.', 'info')
    return redirect(url_for('hr.adjustment_list'))


# ═══════════════════════════════════════════════════════════════════════
# Company Funds (HR summary — reuses ExpenseAccount, no new money-movement code)
# ═══════════════════════════════════════════════════════════════════════

@bp.route('/company-funds')
@login_required
def company_funds():
    accounts = ExpenseAccount.query.filter(ExpenseAccount.staff_id.isnot(None)).order_by(ExpenseAccount.name).all()

    opening_total = sum(a.opening_balance or 0 for a in accounts)
    debit_total = sum(a.total_debit or 0 for a in accounts)
    credit_total = sum(a.total_credit or 0 for a in accounts)
    balance_total = sum(a.balance or 0 for a in accounts)

    return render_template(
        'hr/company_funds.html',
        accounts=accounts, opening_total=opening_total, debit_total=debit_total,
        credit_total=credit_total, balance_total=balance_total, hr_module='hr_funds',
    )


# ═══════════════════════════════════════════════════════════════════════
# Assets & Custody
# ═══════════════════════════════════════════════════════════════════════

@bp.route('/assets')
@login_required
def asset_list():
    assets = Asset.query.filter_by(is_active=True).order_by(Asset.name).all()
    all_assignments = AssetAssignment.query.order_by(AssetAssignment.issued_date.desc()).all()

    assigned_count = sum(1 for a in all_assignments if a.status in ('in_custody', 'overdue'))
    overdue = [a for a in all_assignments if a.status == 'overdue']

    return render_template(
        'hr/asset_list.html',
        assets=assets, assignments=all_assignments,
        assigned_count=assigned_count, overdue_count=len(overdue),
        hr_module='hr_assets',
    )


def _next_asset_sku():
    """Next sequential SKU in the AST-<n> format. Scans existing SKUs
    matching that exact pattern and picks max(n)+1, rather than counting
    rows, so a deleted asset never causes a collision with a still-live one."""
    import re as _re
    max_n = 0
    for (sku,) in db.session.query(Asset.sku).filter(Asset.sku.isnot(None)).all():
        m = _re.match(r'^AST-(\d+)$', sku or '')
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f'AST-{max_n + 1}'


def _asset_category_choices():
    names = [c.name for c in AssetCategory.query.filter_by(is_active=True).order_by(AssetCategory.name).all()]
    return [('', '-- Select category --')] + [(n, n) for n in names]


@bp.route('/assets/add', methods=['GET', 'POST'])
@login_required
@permission_required('hr', action='add')
def add_asset():
    form = AssetForm()
    form.category.choices = _asset_category_choices()
    if request.method == 'GET':
        form.sku.data = _next_asset_sku()

    if form.validate_on_submit():
        asset = Asset(
            name=form.name.data, sku=form.sku.data or _next_asset_sku(), serial_tag=form.serial_tag.data,
            category=form.category.data or None, purchase_date=form.purchase_date.data,
            purchase_cost=form.purchase_cost.data or 0, notes=form.notes.data,
        )
        db.session.add(asset)
        db.session.commit()
        log_activity('HR', f'Asset added: {asset.name}', f'SKU {asset.sku}')
        flash('Asset added.', 'success')
        return redirect(url_for('hr.asset_list'))
    return render_template('hr/asset_form.html', form=form, title='Add Asset')


@bp.route('/assets/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('hr', action='edit')
def edit_asset(id):
    asset = Asset.query.get_or_404(id)
    form = AssetForm(obj=asset)
    form.category.choices = _asset_category_choices()

    if form.validate_on_submit():
        asset.name = form.name.data
        asset.sku = form.sku.data or asset.sku
        asset.serial_tag = form.serial_tag.data
        asset.category = form.category.data or None
        asset.purchase_date = form.purchase_date.data
        asset.purchase_cost = form.purchase_cost.data or 0
        asset.notes = form.notes.data
        db.session.commit()
        log_activity('HR', f'Asset updated: {asset.name}', f'SKU {asset.sku}')
        flash('Asset updated.', 'success')
        return redirect(url_for('hr.asset_list'))
    return render_template('hr/asset_form.html', form=form, title='Edit Asset', asset=asset)


@bp.route('/assets/categories/add', methods=['POST'])
@login_required
@permission_required('hr', action='add')
def add_asset_category():
    """AJAX quick-add: creates a category and returns it as JSON so the
    Add/Edit Asset form's dropdown can pick it up in place, without a full
    page reload losing whatever else the user had already filled in."""
    name = (request.form.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Category name is required.'}), 400

    existing = AssetCategory.query.filter(db.func.lower(AssetCategory.name) == name.lower()).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.session.commit()
        return jsonify({'success': True, 'category': {'id': existing.id, 'name': existing.name}})

    category = AssetCategory(name=name)
    db.session.add(category)
    db.session.commit()
    log_activity('HR', f'Asset category added: {category.name}', '')
    return jsonify({'success': True, 'category': {'id': category.id, 'name': category.name}})


@bp.route('/assets/<int:id>/assign', methods=['GET', 'POST'])
@login_required
@permission_required('hr', action='add')
def assign_asset(id):
    asset = Asset.query.get_or_404(id)
    open_assignment = AssetAssignment.query.filter_by(asset_id=asset.id, returned_date=None).first()
    if open_assignment:
        flash(f'{asset.name} is already assigned to {open_assignment.staff.name} — return it first.', 'warning')
        return redirect(url_for('hr.asset_list'))

    form = AssetAssignmentForm()
    form.staff_id.choices = _active_staff_choices()
    if request.method == 'GET':
        form.issued_date.data = datetime.utcnow().date()

    if form.validate_on_submit():
        assignment = AssetAssignment(
            asset_id=asset.id, staff_id=form.staff_id.data, issued_date=form.issued_date.data,
            condition_out=form.condition_out.data, return_due_date=form.return_due_date.data,
            linked_voucher=form.linked_voucher.data, notes=form.notes.data, created_by=current_user.id,
        )
        db.session.add(assignment)
        db.session.commit()
        log_activity('HR', f'Asset assigned: {asset.name} -> {assignment.staff.name}', '')
        flash('Asset assigned.', 'success')
        return redirect(url_for('hr.asset_list'))

    return render_template('hr/asset_assignment_form.html', form=form, asset=asset)


@bp.route('/assets/assignment/<int:id>/return', methods=['POST'])
@login_required
@permission_required('hr', action='edit')
def return_asset(id):
    assignment = AssetAssignment.query.get_or_404(id)
    assignment.returned_date = datetime.utcnow().date()
    assignment.condition_in = request.form.get('condition_in', '')
    db.session.commit()
    log_activity('HR', f'Asset returned: {assignment.asset.name} from {assignment.staff.name}', '')
    flash('Asset marked returned.', 'success')
    return redirect(url_for('hr.asset_list'))


# ═══════════════════════════════════════════════════════════════════════
# Final Settlements
# ═══════════════════════════════════════════════════════════════════════

def _prior_cleared_settlement(settlement):
    """The most recent CLEARED settlement for this staff member that was
    initiated before this one, if any. A hit means this settlement is for
    someone who left, was cleared, rejoined (see the Rejoin button), and is
    now going through the process again -- surfaced as a "Rejoined staff"
    flag so HR isn't confused by seeing the same name settled twice."""
    return Settlement.query.filter(
        Settlement.staff_id == settlement.staff_id,
        Settlement.id != settlement.id,
        Settlement.status == 'cleared',
        Settlement.initiated_at < settlement.initiated_at,
    ).order_by(Settlement.cleared_at.desc()).first()


@bp.route('/settlements')
@login_required
def settlement_list():
    settlements = Settlement.query.order_by(Settlement.created_at.desc()).all()
    open_count = sum(1 for s in settlements if s.status == 'in_progress')
    awaiting_assets = sum(1 for s in settlements if s.status == 'in_progress' and not s.assets_returned)
    funds_pending = sum(1 for s in settlements if s.status == 'in_progress' and not s.funds_reconciled)
    ready = sum(1 for s in settlements if s.status == 'in_progress' and s.assets_returned and s.funds_reconciled
                and s.last_day_approved and s.attendance_locked and s.advance_confirmed and s.exit_docs_signed)

    # Staff who've left but have no settlement yet -- easy starting point for "Initiate Settlement"
    settled_staff_ids = {s.staff_id for s in settlements}
    left_staff = Staff.query.filter_by(is_active=False).all()
    unsettled_left_staff = [s for s in left_staff if s.id not in settled_staff_ids]

    rejoin_map = {s.id: _prior_cleared_settlement(s) for s in settlements}

    return render_template(
        'hr/settlement_list.html',
        settlements=settlements, open_count=open_count, awaiting_assets=awaiting_assets,
        funds_pending=funds_pending, ready_count=ready, unsettled_left_staff=unsettled_left_staff,
        rejoin_map=rejoin_map, hr_module='hr_settlements',
    )


@bp.route('/settlements/initiate', methods=['GET', 'POST'])
@login_required
@permission_required('hr', action='add')
def initiate_settlement():
    form = SettlementInitiateForm()
    form.staff_id.choices = [(s.id, s.name) for s in Staff.query.order_by(Staff.name).all()]
    preselect = request.args.get('staff_id', type=int)
    if request.method == 'GET' and preselect:
        form.staff_id.data = preselect
        staff = Staff.query.get(preselect)
        if staff and staff.left_date:
            form.last_working_date.data = staff.left_date

    if form.validate_on_submit():
        open_existing = Settlement.query.filter_by(staff_id=form.staff_id.data, status='in_progress').first()
        if open_existing:
            flash('This staff member already has an open settlement in progress.', 'warning')
            return redirect(url_for('hr.settlement_detail', id=open_existing.id))

        settlement = Settlement(
            staff_id=form.staff_id.data, last_working_date=form.last_working_date.data,
            initiated_by=current_user.id, notes=form.notes.data,
        )
        db.session.add(settlement)
        db.session.commit()
        log_activity('HR', f'Settlement initiated: {settlement.staff.name}', f'Last day {settlement.last_working_date}')
        flash('Settlement initiated.', 'success')
        return redirect(url_for('hr.settlement_detail', id=settlement.id))

    return render_template('hr/settlement_form.html', form=form, title='Initiate Settlement')


def _compute_settlement_amounts(settlement):
    staff = settlement.staff
    year_start = settlement.last_working_date.replace(month=1, day=1)
    settlement.salary_through_last_day = staff.get_attendance_earnings(start_date=year_start, end_date=settlement.last_working_date)
    settlement.leave_payout = sum(
        a.earned_amount or 0 for a in staff.attendance_records
        if a.is_paid_leave and year_start <= a.date <= settlement.last_working_date
    )
    settlement.advance_recovery = staff.get_outstanding_advance(end_date=settlement.last_working_date)
    settlement.net_settlement = (
        (settlement.salary_through_last_day or 0)
        - (settlement.advance_recovery or 0)
        - (settlement.other_recovery or 0)
    )


def _company_logo_url(company):
    """Absolute URL for the company logo, so it still resolves correctly
    on a printed page (same convention as purchase._company_logo_url)."""
    if not company or not company.logo_path:
        return None
    return request.host_url.rstrip('/') + '/' + company.logo_path.replace('app/', '').lstrip('/')


@bp.route('/settlements/<int:id>')
@login_required
def settlement_detail(id):
    settlement = Settlement.query.get_or_404(id)
    _compute_settlement_amounts(settlement)
    db.session.commit()
    prior_settlement = _prior_cleared_settlement(settlement)
    company = Company.query.first()
    return render_template('hr/settlement_detail.html', settlement=settlement,
                            prior_settlement=prior_settlement, company=company,
                            logo_url=_company_logo_url(company), hr_module='hr_settlements')


@bp.route('/settlements/<int:id>/toggle-checklist', methods=['POST'])
@login_required
@permission_required('hr', action='edit')
def toggle_settlement_checklist(id):
    settlement = Settlement.query.get_or_404(id)
    field = request.form.get('field')
    allowed = {'last_day_approved', 'attendance_locked', 'funds_reconciled', 'advance_confirmed', 'exit_docs_signed'}
    if field in allowed:
        setattr(settlement, field, not getattr(settlement, field))
        db.session.commit()
    return redirect(url_for('hr.settlement_detail', id=id))


@bp.route('/settlements/<int:id>/clear', methods=['POST'])
@login_required
@permission_required('hr', action='edit')
def clear_settlement(id):
    settlement = Settlement.query.get_or_404(id)
    checklist_complete = all([
        settlement.last_day_approved, settlement.attendance_locked, settlement.funds_reconciled,
        settlement.advance_confirmed, settlement.exit_docs_signed, settlement.assets_returned,
    ])
    if not checklist_complete:
        flash('Complete every checklist item (including asset returns) before clearing this settlement.', 'danger')
        return redirect(url_for('hr.settlement_detail', id=id))

    _compute_settlement_amounts(settlement)
    settlement.status = 'cleared'
    settlement.cleared_by = current_user.id
    settlement.cleared_at = datetime.utcnow()

    # This is the moment the staff member actually "leaves" -- mirrors what
    # salary.mark_staff_left() used to do immediately on a single click.
    # Deliberately deferred to here (settlement cleared) rather than to
    # settlement initiation, so they stay Active -- and keep clocking in,
    # keep their custodian account usable -- through their whole notice
    # period, only dropping off once clearance is actually complete.
    staff = settlement.staff
    staff.is_active = False
    staff.left_date = settlement.last_working_date
    if staff.expense_account:
        staff.expense_account.is_active = False

    db.session.commit()
    log_activity('HR', f'Settlement cleared: {staff.name}', f'Net settlement PKR {settlement.net_settlement}. Staff marked as left ({staff.left_date}).')
    flash(f'Settlement cleared. {staff.name} has been marked as having left the company.', 'success')
    return redirect(url_for('hr.settlement_detail', id=id))


# ═══════════════════════════════════════════════════════════════════════
# Salary Revisions -- full history of every staff member's salary changes
# (previous amount, new amount, effective date, reason), both increases
# and decreases. Writing a row here is also triggered from the plain Edit
# Staff form and from new-hire creation -- see _record_salary_revision()
# and the join-salary row in add_staff(), both in app/routes/salary.py --
# so this page is a complete history regardless of which screen a change
# was made from.
# ═══════════════════════════════════════════════════════════════════════

@bp.route('/salary-revisions')
@login_required
def salary_revision_list():
    query = SalaryRevision.query
    staff_id = request.args.get('staff_id', type=int)
    if staff_id:
        query = query.filter(SalaryRevision.staff_id == staff_id)
    revisions = query.order_by(SalaryRevision.effective_from.desc(), SalaryRevision.id.desc()).all()

    # "Current" = each staff member's most recent revision by effective_from
    latest_id_per_staff = {}
    for r in sorted(revisions, key=lambda r: (r.effective_from, r.id)):
        latest_id_per_staff[r.staff_id] = r.id

    today = datetime.utcnow().date()
    year_start = today.replace(month=1, day=1)
    increases_this_year = [r for r in revisions if r.effective_from >= year_start and r.change_amount > 0]
    total_increase_this_year = sum(r.change_amount for r in increases_this_year)
    staff_revised_this_year = len({r.staff_id for r in increases_this_year})

    return render_template(
        'hr/salary_revision_list.html',
        revisions=revisions, all_staff=_active_staff_choices(),
        selected_staff_id=staff_id, latest_id_per_staff=latest_id_per_staff,
        increases_this_year_count=len(increases_this_year),
        total_increase_this_year=total_increase_this_year,
        staff_revised_this_year=staff_revised_this_year,
        hr_module='hr_salary_revisions',
    )


@bp.route('/salary-revisions/add', methods=['GET', 'POST'])
@login_required
@permission_required('hr', action='add')
def add_salary_revision():
    form = SalaryRevisionForm()
    form.staff_id.choices = _active_staff_choices()
    preselect = request.args.get('staff_id', type=int)
    staff_salary_map = {s.id: s.monthly_salary or 0 for s in Staff.query.filter_by(is_active=True).all()}

    if request.method == 'GET':
        form.effective_from.data = datetime.utcnow().date()
        if preselect:
            form.staff_id.data = preselect

    if form.validate_on_submit():
        staff = Staff.query.get_or_404(form.staff_id.data)
        old_salary = staff.monthly_salary or 0
        new_salary = form.new_salary.data

        if new_salary == old_salary:
            flash('New salary is the same as the current salary — nothing to record.', 'warning')
            return render_template('hr/salary_revision_form.html', form=form, title='Record Salary Revision', staff_salary_map=staff_salary_map)

        revision = SalaryRevision(
            staff_id=staff.id, previous_salary=old_salary, new_salary=new_salary,
            effective_from=form.effective_from.data, reason=form.reason.data,
            approved_by=current_user.id if current_user.is_admin else None,
            created_by=current_user.id,
        )
        db.session.add(revision)
        staff.monthly_salary = new_salary
        staff.calculate_daily_salary()
        db.session.commit()

        direction = 'increase' if revision.change_amount > 0 else 'decrease'
        log_activity('HR', f'Salary {direction}: {staff.name}', f'PKR {old_salary:.2f} -> {new_salary:.2f}')
        flash(f'Salary {direction} recorded for {staff.name}: PKR {old_salary:.2f} -> PKR {new_salary:.2f}.', 'success')
        return redirect(url_for('hr.salary_revision_list'))

    return render_template('hr/salary_revision_form.html', form=form, title='Record Salary Revision', staff_salary_map=staff_salary_map)
