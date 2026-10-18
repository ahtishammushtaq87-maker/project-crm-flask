"""Views for the Sales Target module. Business rules live in services.py
(permissions, validation, periods) and calculations.py (actual sales)."""
from datetime import date, datetime
from functools import wraps
from math import ceil

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError, generate_csrf, validate_csrf
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError

from app import db
from app.models import Product, Salesman, SalesmanGroup
from app.sales_target import bp
from app.sales_target import calculations as calc
from app.sales_target import plans
from app.sales_target import services as svc
from app.sales_target.models import SalesTarget, SalesTargetMember, SalesTargetPlan, SalesTargetProduct
from app.utils import log_activity

PER_PAGE = 15
INVOICES_PER_PAGE = 25


@bp.app_template_filter('sales_target_money')
def money_filter(value):
    if value is None:
        return '—'
    return f'PKR {value:,.2f}'


def _module_view_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not svc.can_view_module(current_user):
            flash('You do not have permission to view Sales Targets.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return wrapper


def _check_csrf():
    try:
        validate_csrf(request.form.get('csrf_token'))
    except (ValidationError, CSRFError):
        return False
    return True


def _get_visible_target(target_id):
    """404 for missing targets and for ones this user may not see, so ids
    can't be probed."""
    target = db.session.get(SalesTarget, target_id)
    if target is None or not svc.can_view_target(current_user, target):
        abort(404)
    return target


# ── Dashboard ──────────────────────────────────────────────────────────────

@bp.route('/')
@_module_view_required
def index():
    args = request.args
    preset, p_start, p_end, period_label = svc.resolve_period(
        args.get('period', 'this_month'), args.get('start_date'), args.get('end_date'))
    search = (args.get('q') or '').strip()[:100]
    status = args.get('status', '')
    status = status if status in SalesTarget.STATUSES else ''
    ttype = args.get('type', '')
    ttype = ttype if ttype in SalesTarget.TYPES else ''
    show_profit = svc.can_view_profit(current_user)
    sort = args.get('sort', 'end_date')
    if sort not in svc.SORT_KEYS or (sort == 'profit' and not show_profit):
        sort = 'end_date'
    direction = 'asc' if args.get('dir') == 'asc' else 'desc'
    page = max(args.get('page', 1, type=int) or 1, 1)

    base = svc.visible_targets_query(current_user)
    has_any_target = db.session.query(base.exists()).scalar()

    query = svc.overlaps_period(base, p_start, p_end)
    if status:
        query = query.filter(SalesTarget.status == status)
    if ttype:
        query = query.filter(SalesTarget.target_type == ttype)
    if search:
        like = f'%{search}%'
        member_match = SalesTarget.members.any(
            SalesTargetMember.salesman.has(Salesman.name.ilike(like)))
        item_match = SalesTarget.products.any(SalesTargetProduct.product.has(
            or_(Product.name.ilike(like), Product.sku.ilike(like))))
        query = query.filter(or_(SalesTarget.name.ilike(like),
                                 SalesTarget.salesman.has(Salesman.name.ilike(like)),
                                 member_match, item_match))

    try:
        perfs = svc.compute_all(query.all())
    except SQLAlchemyError:
        current_app.logger.exception('Sales Target: could not calculate performance')
        flash('Sales figures could not be calculated right now. Please try again.', 'danger')
        perfs = []

    # KPI cards: one target type at a time (see services.summarize).
    types_present = [t for t in SalesTarget.TYPES
                     if any(p['target'].target_type == t and p['target'].status in SalesTarget.COUNTED_STATUSES
                            for p in perfs)]
    kpi_type = ttype or args.get('kpi', '')
    if kpi_type not in SalesTarget.TYPES:
        kpi_type = next((t for t in (SalesTarget.TYPE_COMPANY, SalesTarget.TYPE_INDIVIDUAL, SalesTarget.TYPE_TEAM)
                         if t in types_present), SalesTarget.TYPE_COMPANY)
    summary = svc.summarize(perfs, kpi_type)

    perfs.sort(key=svc.SORT_KEYS[sort], reverse=(direction == 'desc'))
    total = len(perfs)
    pages = max(ceil(total / PER_PAGE), 1)
    page = min(page, pages)
    page_rows = perfs[(page - 1) * PER_PAGE: page * PER_PAGE]

    filters = {'period': preset, 'start_date': args.get('start_date', '') if preset == 'custom' else '',
               'end_date': args.get('end_date', '') if preset == 'custom' else '',
               'q': search, 'status': status, 'type': ttype, 'sort': sort, 'dir': direction}

    return render_template(
        'sales_target/index.html',
        rows=page_rows, total=total, page=page, pages=pages, per_page=PER_PAGE,
        summary=summary, types_present=types_present,
        filters=filters, period_label=period_label, period_choices=svc.PERIOD_CHOICES,
        has_any_target=has_any_target, show_profit=show_profit,
        is_filtered=bool(search or status or ttype),
        can_add=svc.can_manage(current_user, 'add'),
        can_edit=svc.can_manage(current_user, 'edit'),
        can_delete=svc.can_manage(current_user, 'delete'),
        scope_label=svc.scope_label, items_label=svc.items_label, initials=svc.initials,
        csrf_token_value=generate_csrf(),
        statuses=SalesTarget.STATUSES, status_labels=SalesTarget.STATUS_LABELS,
        types=SalesTarget.TYPES, type_labels=SalesTarget.TYPE_LABELS,
    )


# ── Create / edit ──────────────────────────────────────────────────────────

def _form_context(target=None, values=None, errors=None, grid_errors=None):
    salesmen = Salesman.query.order_by(Salesman.name).all()
    groups = SalesmanGroup.query.filter_by(is_active=True).order_by(SalesmanGroup.name).all()
    today = date.today()
    if values is None:
        if target:
            values = {
                'name': target.name, 'target_type': target.target_type,
                'target_amount': f'{target.target_amount:.2f}',
                'bonus_amount': f'{target.bonus_amount:.2f}' if target.bonus_amount is not None else '',
                'start_date': target.start_date.isoformat(), 'end_date': target.end_date.isoformat(),
                'salesman_id': target.salesman_id, 'member_ids': target.member_ids,
                'product_ids': target.product_ids,
                'status': target.status, 'description': target.description or '',
            }
        else:
            start = today.replace(day=1)
            _, _, end, _ = svc.resolve_period('this_month', today=today)
            values = {'name': f'{today.strftime("%B %Y")} Sales Target', 'target_type': 'individual',
                      'target_amount': '', 'bonus_amount': '', 'start_date': start.isoformat(),
                      'end_date': end.isoformat(), 'salesman_id': None, 'member_ids': [],
                      'product_ids': [],
                      'status': 'active', 'description': ''}
    values.setdefault('period_mode', 'single')
    values.setdefault('split_items', False)
    values.setdefault('plan_year', today.year)
    values.setdefault('plan_start_month', 1)
    values.setdefault('plan_split', 'month')
    values.setdefault('plan_count', 12)
    values.setdefault('grid', {})
    # Finished items for the dropdown, plus any already on the target that
    # have since stopped being finished/active (so editing never drops them).
    items = svc.finished_items_query().order_by(Product.name).all()
    extra_ids = set(values.get('product_ids') or []) - {p.id for p in items}
    if extra_ids:
        items += Product.query.filter(Product.id.in_(extra_ids)).order_by(Product.name).all()
    return dict(
        target=target, values=values, errors=errors or {},
        salesmen=salesmen, groups=groups, finished_items=items,
        removed_items=target.removed_product_count if target else 0,
        types=svc.form_target_types(target), type_labels=SalesTarget.TYPE_LABELS,
        statuses=SalesTarget.STATUSES, status_labels=SalesTarget.STATUS_LABELS,
        locked=bool(target and target.is_closed),
        csrf_token_value=generate_csrf(), form_nonce=svc.issue_form_nonce(),
        year_choices=plans.year_choices(today), months=plans.MONTHS, grid_errors=grid_errors or {},
        plan_part=target.plan_part if target else None,
    )


def _submitted_values():
    f = request.form
    return {
        'name': f.get('name', ''), 'target_type': f.get('target_type', ''),
        'target_amount': f.get('target_amount', ''), 'bonus_amount': f.get('bonus_amount', ''),
        'start_date': f.get('start_date', ''), 'end_date': f.get('end_date', ''),
        'salesman_id': svc._parse_int(f.get('salesman_id')),
        'member_ids': [i for i in (svc._parse_int(v) for v in f.getlist('member_ids')) if i],
        'product_ids': [i for i in (svc._parse_int(v) for v in f.getlist('product_ids')) if i],
        'status': f.get('status', ''), 'description': f.get('description', ''),
        'period_mode': 'yearly' if f.get('period_mode') == 'yearly' else 'single',
        'split_items': f.get('split_items') == '1',
        'plan_year': svc._parse_int(f.get('plan_year')) or date.today().year,
        'plan_start_month': svc._parse_int(f.get('plan_start_month')) or 1,
        'plan_split': 'quarter' if f.get('plan_split') == 'quarter' else 'month',
        'plan_count': svc._parse_int(f.get('plan_count')) or 12,
        'grid': plans.grid_state(f),
    }


def _apply(target, data):
    target.name = data['name']
    target.description = data['description']
    target.status = data['status']
    target.target_type = data['target_type']
    target.target_amount = float(data['target_amount'])
    target.bonus_amount = float(data['bonus_amount']) if data['bonus_amount'] is not None else None
    target.start_date = data['start_date']
    target.end_date = data['end_date']
    target.salesman_id = data['salesman_id']
    wanted = set(data['member_ids'])
    for m in list(target.members):
        if m.salesman_id not in wanted:
            target.members.remove(m)
    have = {m.salesman_id for m in target.members}
    for sid in sorted(wanted - have):
        target.members.append(SalesTargetMember(salesman_id=sid))
    wanted_products = set(data['product_ids'])
    keep_removed = data.get('keep_removed_products', 0)
    for p in list(target.products):
        if p.product_id is None and keep_removed:
            keep_removed -= 1
        elif p.product_id not in wanted_products:
            target.products.remove(p)
    have_products = {p.product_id for p in target.products}
    for pid in sorted(wanted_products - have_products):
        target.products.append(SalesTargetProduct(product_id=pid))
    target.updated_by = current_user.id
    target.updated_at = datetime.utcnow()


def _save_form(target):
    """Shared POST handling for create and edit. Returns a response."""
    is_new = target is None
    if not _check_csrf():
        flash('Your session expired. Please submit the form again.', 'danger')
        return render_template('sales_target/form.html', **_form_context(target, _submitted_values()))
    if not svc.consume_form_nonce(request.form.get('form_nonce')):
        flash('This form was already submitted. Check the target list before trying again.', 'warning')
        return redirect(url_for('sales_target.index', period='all'))

    if is_new and plans.is_bulk_request(request.form):
        return _save_bulk()

    data, errors = svc.validate_target_form(request.form, existing=target)
    if errors:
        flash(errors.get('__all__') or 'Please correct the highlighted fields.', 'danger')
        return render_template('sales_target/form.html',
                               **_form_context(target, _submitted_values(), errors)), 400

    if is_new:
        target = SalesTarget(created_by=current_user.id)
        db.session.add(target)
    _apply(target, data)
    try:
        db.session.commit()  # target + members in one transaction
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Sales Target: save failed')
        flash('The target could not be saved because of a database error. Please try again.', 'danger')
        return render_template('sales_target/form.html',
                               **_form_context(None if is_new else target, _submitted_values())), 500

    verb = 'Created' if is_new else 'Updated'
    log_activity('Sales', f'{verb} Sales Target: {target.name}',
                 f'ID: {target.id}, {target.type_label}, PKR {target.target_amount:,.2f}, '
                 f'{target.start_date} to {target.end_date}, status {target.status}')
    if data['locked'] and not is_new:
        flash('Target updated. Amount, period and assignment stay locked while it is '
              f'{target.status_label.lower()}; set it back to Active to change them.', 'success')
    else:
        flash(f'Target "{target.name}" {verb.lower()} successfully.', 'success')
    return redirect(url_for('sales_target.detail', target_id=target.id))


def _save_bulk():
    """Create a yearly plan (12 months) and/or one target per item."""
    data, errors, grid_errors = plans.validate_create(request.form)
    if errors:
        flash(errors.get('__all__') or errors.get('grid') or 'Please correct the highlighted fields.', 'danger')
        return render_template('sales_target/form.html',
                               **_form_context(None, _submitted_values(), errors, grid_errors)), 400
    plan, created = plans.create(data, current_user.id)
    try:
        db.session.commit()  # plan + every target in one transaction
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Sales Target: bulk save failed')
        flash('The targets could not be saved because of a database error. Please try again.', 'danger')
        return render_template('sales_target/form.html', **_form_context(None, _submitted_values())), 500

    total = sum((calc.to_money(t.target_amount) for t in created), calc.to_money(0))
    what = f'plan "{plan.name}"' if plan else f'targets "{data["base"]["name"]}"'
    log_activity('Sales', f'Created Sales Target {what}',
                 f'{len(created)} target(s), PKR {total:,.2f} in total' + (f', plan ID {plan.id}' if plan else ''))
    flash(f'Created {len(created)} target{"" if len(created) == 1 else "s"} '
          f'(PKR {total:,.2f} in total).', 'success')
    if plan:
        return redirect(url_for('sales_target.plan_view', plan_id=plan.id))
    if len(created) == 1:
        return redirect(url_for('sales_target.detail', target_id=created[0].id))
    return redirect(url_for('sales_target.index', period='all', q=data['base']['name']))


@bp.route('/create', methods=['GET', 'POST'])
@_module_view_required
def create():
    if not svc.can_manage(current_user, 'add'):
        flash('You do not have permission to create sales targets.', 'danger')
        return redirect(url_for('sales_target.index'))
    if request.method == 'POST':
        return _save_form(None)
    return render_template('sales_target/form.html', **_form_context())


@bp.route('/<int:target_id>/edit', methods=['GET', 'POST'])
@_module_view_required
def edit(target_id):
    target = _get_visible_target(target_id)
    if not svc.can_manage(current_user, 'edit'):
        flash('You do not have permission to edit sales targets.', 'danger')
        return redirect(url_for('sales_target.detail', target_id=target.id))
    if request.method == 'POST':
        return _save_form(target)
    return render_template('sales_target/form.html', **_form_context(target))


# ── Detail ─────────────────────────────────────────────────────────────────

@bp.route('/<int:target_id>')
@_module_view_required
def detail(target_id):
    target = _get_visible_target(target_id)
    page = max(request.args.get('page', 1, type=int) or 1, 1)
    perf = calc.performance(target)
    pagination, invoices, excluded, econ, reached_by = None, [], {}, None, None
    if perf['available']:
        try:
            pagination, invoices = calc.contributing_invoices(
                target, page=page, per_page=INVOICES_PER_PAGE,
                restrict_salesman_ids=svc.scoped_salesman_ids(current_user))
            excluded = calc.exclusions(target)
            econ = calc.economics(target, actual=perf['actual'])
            running, reached_by = calc.running_achievement(target)
            calc.annotate_invoices(target, invoices, econ, running)
        except SQLAlchemyError:
            current_app.logger.exception('Sales Target: could not load invoices')
            flash('Contributing invoices could not be loaded right now.', 'danger')
    plan_part = target.plan_part
    plan_siblings = []
    if plan_part:
        plan_siblings = sorted((p for p in plan_part.plan.parts
                                if p.row_no == plan_part.row_no and p.target is not None),
                               key=lambda p: p.period_no)
    # "Monthly" / "Quarterly" for plan parts and whole calendar months.
    if plan_part:
        period_kind = 'Monthly' if plan_part.plan.is_monthly else 'Quarterly'
    else:
        _, _, month_end, _ = svc.resolve_period('this_month', today=target.start_date)
        period_kind = ('Monthly' if target.start_date.day == 1 and target.end_date == month_end
                       else 'Custom period')
    scope = svc.scope_label(target)
    return render_template(
        'sales_target/detail.html',
        period_kind=period_kind, initials=svc.initials(scope),
        can_add=svc.can_manage(current_user, 'add'),
        period_choices=svc.PERIOD_CHOICES, statuses=SalesTarget.STATUSES,
        status_labels=SalesTarget.STATUS_LABELS, types=SalesTarget.TYPES, type_labels=SalesTarget.TYPE_LABELS,
        plan_part=plan_part, plan_siblings=plan_siblings,
        plan_periods=plans.plan_periods(plan_part.plan) if plan_part else [],
        target=target, perf=perf, pagination=pagination, invoices=invoices, excluded=excluded,
        econ=econ, reached_by=reached_by, show_profit=svc.can_view_profit(current_user),
        scope_label=scope, items_label=svc.items_label(target),
        can_edit=svc.can_manage(current_user, 'edit'),
        can_delete=svc.can_manage(current_user, 'delete'),
        can_open_invoices=current_user.has_permission('sales', 'view'),
        last_invoice=invoices[0] if invoices and page == 1 else None,
        csrf_token_value=generate_csrf(),
    )


# ── Delete ─────────────────────────────────────────────────────────────────

@bp.route('/<int:target_id>/delete', methods=['POST'])
@_module_view_required
def delete(target_id):
    target = _get_visible_target(target_id)
    if not svc.can_manage(current_user, 'delete'):
        flash('You do not have permission to delete sales targets.', 'danger')
        return redirect(url_for('sales_target.detail', target_id=target.id))
    if not _check_csrf():
        flash('Your session expired. Please try deleting again.', 'danger')
        return redirect(url_for('sales_target.detail', target_id=target.id))
    name, tid = target.name, target.id
    plan = target.plan_part.plan if target.plan_part else None
    try:
        db.session.delete(target)  # members, items and plan link go with it (cascade)
        db.session.flush()
        if plan is not None:
            db.session.expire(plan, ['parts'])
            if not plan.parts:  # last quarter of a yearly plan: drop the empty plan
                db.session.delete(plan)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Sales Target: delete failed')
        flash('The target could not be deleted because of a database error.', 'danger')
        return redirect(url_for('sales_target.detail', target_id=tid))
    log_activity('Sales', f'Deleted Sales Target: {name}', f'ID: {tid}')
    flash(f'Target "{name}" deleted.', 'success')
    return redirect(url_for('sales_target.index'))


# ── Yearly plans (a yearly target split into quarters) ─────────────────────

def _get_visible_plan(plan_id):
    plan = db.session.get(SalesTargetPlan, plan_id)
    targets = plans.plan_targets(plan) if plan else []
    if plan is None or not targets or not all(svc.can_view_target(current_user, t) for t in targets):
        abort(404)
    return plan, targets


@bp.route('/plan/<int:plan_id>')
@_module_view_required
def plan_view(plan_id):
    plan, targets = _get_visible_plan(plan_id)
    try:
        report = plans.plan_performance(plan)
    except SQLAlchemyError:
        current_app.logger.exception('Sales Target: could not calculate plan performance')
        flash('Sales figures could not be calculated right now. Please try again.', 'danger')
        return redirect(url_for('sales_target.index'))
    first = targets[0]
    return render_template(
        'sales_target/plan.html', plan=plan, report=report, first=first,
        year_label=plans.plan_span_label(plan),
        scope_label=svc.scope_label(first), can_edit=svc.can_manage(current_user, 'edit'),
        unit_words=plans.unit_words(plan),
        can_edit_split=any(not t.is_closed for t in targets),
    )


@bp.route('/plan/<int:plan_id>/edit', methods=['GET', 'POST'])
@_module_view_required
def plan_edit(plan_id):
    plan, targets = _get_visible_plan(plan_id)
    if not svc.can_manage(current_user, 'edit'):
        flash('You do not have permission to edit sales targets.', 'danger')
        return redirect(url_for('sales_target.plan_view', plan_id=plan.id))
    periods, rows = plans.plan_layout(plan)
    unit, units = plans.unit_words(plan)

    def render(errors=None, posted=None, code=200):
        return render_template(
            'sales_target/plan_edit.html', plan=plan, periods=periods, rows=rows, unit=unit, units=units,
            year_label=plans.plan_span_label(plan), scope_label=svc.scope_label(targets[0]),
            errors=errors or {}, posted=posted, csrf_token_value=generate_csrf(),
            form_nonce=svc.issue_form_nonce()), code

    if request.method == 'GET':
        return render()
    if not _check_csrf():
        flash('Your session expired. Please submit the form again.', 'danger')
        return render(posted=request.form)
    if not svc.consume_form_nonce(request.form.get('form_nonce')):
        flash('This form was already submitted. Check the plan before trying again.', 'warning')
        return redirect(url_for('sales_target.plan_view', plan_id=plan.id))

    updates, errors = plans.validate_plan_edit(plan, request.form)
    if errors:
        flash(next(iter(errors.values())), 'danger')
        return render(errors, request.form, 400)
    now = datetime.utcnow()
    changed = 0
    for t, amount in updates.items():
        if calc.to_money(t.target_amount) != amount:
            t.target_amount = float(amount)
            t.updated_by, t.updated_at = current_user.id, now
            changed += 1
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Sales Target: plan update failed')
        flash(f'The {unit} targets could not be saved because of a database error. Please try again.', 'danger')
        return render(posted=request.form, code=500)
    log_activity('Sales', f'Updated Sales Target yearly plan: {plan.name}',
                 f'Plan ID {plan.id}, {changed} {unit} target(s) changed')
    flash(f'{unit.capitalize()} targets saved.' if changed else 'No amounts were changed.', 'success')
    return redirect(url_for('sales_target.plan_view', plan_id=plan.id))
