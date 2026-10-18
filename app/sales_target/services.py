"""Permissions, validation, reporting periods and KPI aggregation for the
Sales Target module. Every route goes through these helpers; anything the
browser sends (amount, status, salesman, ids) is re-validated here.

Permissions reuse existing User flags, so no new columns are needed:
  view            admin, or can_view_targets AND can_view_sales (target pages
                  show invoice amounts, so sales visibility is required too).
  create/edit/del admin, or can_add/edit/delete_targets, and the user isn't
                  salesperson-scoped (see below).
Salesperson scope, the convention Sales Recovery uses: a non-admin whose login
is linked to one or more Salesman records (Salesman.user_id) is a salesperson.
They see only individual targets assigned to their own salesman record(s), and
can't create or change targets, so nobody can set their own target.
"""
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import session

from app import db
from app.models import Product, Salesman
from app.sales_target.calculations import margin_pct as calc_margin, performance, to_money
from app.sales_target.models import SalesTarget

MAX_AMOUNT = Decimal('1000000000000')  # 1 trillion, a sanity cap
MAX_ITEMS = 200


def finished_items_query():
    """Finished goods, as the CRM defines them elsewhere (Product
    Development): manufactured, active, not obsolete."""
    return Product.query.filter(Product.is_manufactured == True,  # noqa: E712
                                Product.is_active == True,  # noqa: E712
                                Product.is_obsolete == False)  # noqa: E712


# ── Permissions ────────────────────────────────────────────────────────────

def _is_admin(user):
    return getattr(user, 'role', '') == 'admin'


def scoped_salesman_ids(user):
    """None = unrestricted; otherwise the salesman ids this user is limited to."""
    if _is_admin(user):
        return None
    linked = {s.id for s in (getattr(user, 'linked_salesmen', None) or [])}
    return linked or None


def can_view_module(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    return _is_admin(user) or (bool(getattr(user, 'can_view_targets', False))
                               and bool(getattr(user, 'can_view_sales', False)))


def can_manage(user, action):
    """action: 'add' | 'edit' | 'delete'."""
    if not can_view_module(user):
        return False
    if _is_admin(user):
        return True
    return bool(getattr(user, f'can_{action}_targets', False)) and scoped_salesman_ids(user) is None


def can_view_profit(user):
    """Cost and profit are shown to admins and to users with Profit & Loss
    access (the same flag that guards the P&L pages); others see sales only."""
    return can_view_module(user) and (_is_admin(user) or bool(getattr(user, 'can_view_profit_loss', False)))


def can_view_target(user, target):
    if not can_view_module(user):
        return False
    ids = scoped_salesman_ids(user)
    if ids is None:
        return True
    return target.target_type == SalesTarget.TYPE_INDIVIDUAL and target.salesman_id in ids


def visible_targets_query(user):
    query = SalesTarget.query
    ids = scoped_salesman_ids(user)
    if ids is not None:
        query = query.filter(SalesTarget.target_type == SalesTarget.TYPE_INDIVIDUAL,
                             SalesTarget.salesman_id.in_(ids))
    return query


# ── Duplicate-submission guard ──────────────────────────────────────────────
# Each rendered form carries a one-time token kept in the session. A second
# POST with the same token (double click, refresh-resubmit) is rejected.

_NONCE_KEY = 'sales_target_form_nonces'


def issue_form_nonce():
    nonce = secrets.token_urlsafe(16)
    nonces = [n for n in session.get(_NONCE_KEY, []) if n != nonce][-19:]
    nonces.append(nonce)
    session[_NONCE_KEY] = nonces
    return nonce


def consume_form_nonce(nonce):
    nonces = session.get(_NONCE_KEY, [])
    if not nonce or nonce not in nonces:
        return False
    nonces.remove(nonce)
    session[_NONCE_KEY] = nonces
    return True


# ── Validation ─────────────────────────────────────────────────────────────

def _parse_money(raw, field, errors, required=True):
    raw = (raw or '').strip().replace(',', '')
    if not raw:
        if required:
            errors[field] = 'Enter an amount.'
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        errors[field] = 'Enter a valid number, e.g. 250000.'
        return None
    if not value.is_finite():
        errors[field] = 'Enter a valid number, e.g. 250000.'
        return None
    if value.as_tuple().exponent < -2:
        errors[field] = 'Use at most two decimal places.'
        return None
    if value > MAX_AMOUNT:
        errors[field] = 'Amount is too large.'
        return None
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _parse_date(raw, field, errors, label):
    raw = (raw or '').strip()
    if not raw:
        errors[field] = f'Choose a {label}.'
        return None
    try:
        value = datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        errors[field] = f'Enter a valid {label} (YYYY-MM-DD).'
        return None
    if not (2000 <= value.year <= 2100):
        errors[field] = f'{label.capitalize()} must be between 2000 and 2100.'
        return None
    return value


def _parse_int(raw):
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def form_target_types(existing=None):
    """Types offered on the create/edit form. New targets are Individual
    Salesman only; an existing Team or Company-wide target keeps its own type
    so it can still be edited."""
    types = [SalesTarget.TYPE_INDIVIDUAL]
    if existing is not None and existing.target_type in SalesTarget.TYPES and existing.target_type not in types:
        types.append(existing.target_type)
    return types


def validate_target_form(form, existing=None, today=None, check_duplicate=True):
    """Return (data, errors). ``form`` is request.form. ``data`` holds clean,
    typed values ready to save; ``errors`` maps field name -> message.
    check_duplicate=False is for yearly plans, which check each quarter."""
    today = today or date.today()
    errors = {}
    data = {}

    name = (form.get('name') or '').strip()
    if not name:
        errors['name'] = 'Enter a target name.'
    elif len(name) > 150:
        errors['name'] = 'Keep the name under 150 characters.'
    data['name'] = name

    description = (form.get('description') or '').strip()
    if len(description) > 2000:
        errors['description'] = 'Keep the notes under 2,000 characters.'
    data['description'] = description or None

    status = (form.get('status') or '').strip().lower()
    if status not in SalesTarget.STATUSES:
        errors['status'] = 'Choose a valid status.'
    data['status'] = status

    # Closed targets (completed/cancelled) keep their amount, period and scope;
    # only the name, notes and status may change. Reopening (status back to
    # draft/active) unlocks everything.
    locked = bool(existing and existing.is_closed and status in SalesTarget.CLOSED_STATUSES)
    data['locked'] = locked
    if locked:
        data.update(
            target_type=existing.target_type,
            target_amount=to_money(existing.target_amount),
            bonus_amount=to_money(existing.bonus_amount) if existing.bonus_amount is not None else None,
            start_date=existing.start_date,
            end_date=existing.end_date,
            salesman_id=existing.salesman_id,
            member_ids=existing.member_ids,
            product_ids=existing.product_ids,
            keep_removed_products=existing.removed_product_count,
        )
    else:
        target_type = (form.get('target_type') or '').strip().lower()
        if target_type not in form_target_types(existing):
            errors['target_type'] = 'Choose a target type.'
        data['target_type'] = target_type

        amount = _parse_money(form.get('target_amount'), 'target_amount', errors)
        if amount is not None and amount <= 0:
            errors['target_amount'] = 'Target amount must be greater than zero.'
        data['target_amount'] = amount

        bonus = _parse_money(form.get('bonus_amount'), 'bonus_amount', errors, required=False)
        if bonus is not None and bonus < 0:
            errors['bonus_amount'] = 'Bonus cannot be negative.'
        data['bonus_amount'] = bonus

        start = _parse_date(form.get('start_date'), 'start_date', errors, 'start date')
        end = _parse_date(form.get('end_date'), 'end_date', errors, 'end date')
        if start and end and end < start:
            errors['end_date'] = 'End date cannot be before the start date.'
        data['start_date'], data['end_date'] = start, end

        data['salesman_id'] = None
        data['member_ids'] = []
        if target_type == SalesTarget.TYPE_INDIVIDUAL:
            sid = _parse_int(form.get('salesman_id'))
            salesman = db.session.get(Salesman, sid) if sid else None
            keeping_current = existing is not None and existing.salesman_id == sid
            if not salesman:
                errors['salesman_id'] = 'Choose the salesman this target is for.'
            elif not salesman.is_active and not keeping_current:
                errors['salesman_id'] = 'This salesman is inactive. Choose an active salesman.'
            else:
                data['salesman_id'] = salesman.id
        elif target_type == SalesTarget.TYPE_TEAM:
            raw_ids = {i for i in (_parse_int(v) for v in form.getlist('member_ids')) if i}
            current = set(existing.member_ids) if existing else set()
            found = Salesman.query.filter(Salesman.id.in_(raw_ids)).all() if raw_ids else []
            valid = {s.id for s in found if s.is_active or s.id in current}
            if raw_ids - valid:
                errors['member_ids'] = 'One or more selected salesmen are not available.'
            elif len(valid) < 2:
                errors['member_ids'] = 'Choose at least two salesmen for a team target (use Individual for one).'
            data['member_ids'] = sorted(valid)

        # Optional: limit the target to chosen finished items (none = all sales).
        raw_pids = {i for i in (_parse_int(v) for v in form.getlist('product_ids')) if i}
        current_pids = set(existing.product_ids) if existing else set()
        if len(raw_pids) > MAX_ITEMS:
            errors['product_ids'] = f'Choose at most {MAX_ITEMS} items.'
            raw_pids = set()
        new_pids = raw_pids - current_pids
        allowed_new = ({p.id for p in finished_items_query().filter(Product.id.in_(new_pids)).all()}
                       if new_pids else set())
        kept = {p.id for p in Product.query.filter(Product.id.in_(raw_pids & current_pids)).all()}             if raw_pids & current_pids else set()
        if new_pids - allowed_new or (raw_pids & current_pids) - kept:
            errors['product_ids'] = 'One or more selected items are not available as finished items.'
        data['product_ids'] = sorted(allowed_new | kept)
        data['keep_removed_products'] = 0

    # Completed means the period is over; it is never set automatically and
    # can't be chosen while the period is still running.
    end = data.get('end_date')
    if status == 'completed' and end and end >= today and 'status' not in errors:
        errors['status'] = ('A target can be marked Completed only after its end date '
                            f'({end.strftime("%d %b %Y")}) has passed.')

    if not errors and check_duplicate:
        dup = find_duplicate(data, exclude_id=existing.id if existing else None)
        if dup:
            errors['__all__'] = (f'A target with the same scope and period already exists: "{dup.name}". '
                                 'Edit that target instead of creating a duplicate.')
    return data, errors


def find_duplicate(data, exclude_id=None):
    """Same type, scope and exact period, not cancelled."""
    query = SalesTarget.query.filter(
        SalesTarget.target_type == data['target_type'],
        SalesTarget.start_date == data['start_date'],
        SalesTarget.end_date == data['end_date'],
        SalesTarget.status != 'cancelled',
    )
    if exclude_id:
        query = query.filter(SalesTarget.id != exclude_id)
    if data['target_type'] == SalesTarget.TYPE_INDIVIDUAL:
        query = query.filter(SalesTarget.salesman_id == data['salesman_id'])
    for t in query.all():
        if data['target_type'] == SalesTarget.TYPE_TEAM and t.member_ids != data['member_ids']:
            continue
        if t.product_ids != data.get('product_ids', []) or t.removed_product_count:
            continue
        return t
    return None


# ── Reporting periods ──────────────────────────────────────────────────────

PERIOD_CHOICES = (
    ('this_month', 'This Month'),
    ('last_month', 'Last Month'),
    ('this_quarter', 'This Quarter'),
    ('this_year', 'This Year'),
    ('all', 'All Periods'),
    ('custom', 'Custom Range'),
)


def resolve_period(preset, start_raw=None, end_raw=None, today=None):
    """Return (preset, start, end, label). start/end are None for 'all'."""
    today = today or date.today()
    first_this_month = today.replace(day=1)
    if preset == 'last_month':
        end = first_this_month - timedelta(days=1)
        start = end.replace(day=1)
    elif preset == 'this_quarter':
        q_month = 3 * ((today.month - 1) // 3) + 1
        start = date(today.year, q_month, 1)
        end = (date(today.year + (q_month + 2) // 12, (q_month + 2) % 12 + 1, 1) - timedelta(days=1))
    elif preset == 'this_year':
        start, end = date(today.year, 1, 1), date(today.year, 12, 31)
    elif preset == 'all':
        return 'all', None, None, 'All periods'
    elif preset == 'custom':
        errors = {}
        start = _parse_date(start_raw, 's', errors, 'start date') if start_raw else None
        end = _parse_date(end_raw, 'e', errors, 'end date') if end_raw else None
        if start and end and end < start:
            start, end = end, start
        if not start and not end:
            return 'all', None, None, 'All periods'
        label = f'{start.strftime("%d %b %Y") if start else "Any"} – {end.strftime("%d %b %Y") if end else "Any"}'
        return 'custom', start, end, label
    else:
        preset = 'this_month'
        start = first_this_month
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return preset, start, end, f'{start.strftime("%d %b %Y")} – {end.strftime("%d %b %Y")}'


def overlaps_period(query, start, end):
    """Targets whose own period overlaps the selected period. Saved target
    dates are never modified by the filter."""
    if start:
        query = query.filter(SalesTarget.end_date >= start)
    if end:
        query = query.filter(SalesTarget.start_date <= end)
    return query


# ── KPI aggregation ────────────────────────────────────────────────────────

def summarize(perfs, kpi_type):
    """Aggregate KPI cards for ONE target type, counted statuses only.

    Each target is measured over its own Target Period, and the cards add
    those per-target figures up. Mixing types would count the same invoice
    in a company target and in an individual target, hence one type at a time.
    """
    rows = [p for p in perfs
            if p['target'].target_type == kpi_type
            and p['target'].status in SalesTarget.COUNTED_STATUSES]
    usable = [p for p in rows if p['available']]
    total_target = sum((p['target_amount'] for p in usable), Decimal('0.00'))
    actual = sum((p['actual'] for p in usable), Decimal('0.00'))
    exceeded = sum((p['exceeded'] for p in usable), Decimal('0.00'))
    remaining = sum((p['remaining'] for p in usable), Decimal('0.00'))
    ach = (actual / total_target * 100).quantize(Decimal('0.1')) if total_target > 0 else None
    econs = [p['economics'] for p in usable if p.get('economics')]
    selling = sum((e['selling'] for e in econs), Decimal('0.00'))
    cost = sum((e['cost'] for e in econs), Decimal('0.00'))
    if ach is None:
        tone = 'muted'
    elif ach >= 100:
        tone = 'good'
    elif ach >= 80:
        tone = 'warn'
    else:
        tone = 'bad'
    return {
        'type': kpi_type,
        'type_label': SalesTarget.TYPE_LABELS[kpi_type],
        'count': len(usable),
        'unavailable': len(rows) - len(usable),
        'total_target': total_target,
        'actual': actual,
        'achievement': ach,
        'remaining': remaining,
        'exceeded': exceeded,
        'tone': tone,
        'overlap_warning': _has_scope_overlap([p['target'] for p in usable]),
        'has_economics': bool(econs),
        'selling': selling,
        'cost': cost,
        'profit': selling - cost,
        'margin': calc_margin(selling - cost, selling),
    }


def _has_scope_overlap(targets):
    """True if two targets cover the same invoices for overlapping dates, so
    the same sale counts toward both."""
    for i, a in enumerate(targets):
        for b in targets[i + 1:]:
            if a.start_date > b.end_date or b.start_date > a.end_date:
                continue
            if a.target_type == SalesTarget.TYPE_COMPANY:
                return True
            if a.target_type == SalesTarget.TYPE_INDIVIDUAL and a.salesman_id == b.salesman_id:
                return True
            if a.target_type == SalesTarget.TYPE_TEAM and set(a.member_ids) & set(b.member_ids):
                return True
    return False


def compute_all(targets, today=None, with_economics=True):
    today = today or date.today()
    return [performance(t, today=today, with_economics=with_economics) for t in targets]


SORT_KEYS = {
    'end_date': lambda p: (p['target'].end_date, p['target'].id),
    'amount': lambda p: (p['target_amount'], p['target'].id),
    'actual': lambda p: (p['actual'] if p['actual'] is not None else Decimal('-1'), p['target'].id),
    'achievement': lambda p: (p['achievement'] if p['achievement'] is not None else Decimal('-1'), p['target'].id),
    'remaining': lambda p: (p['remaining'] if p['remaining'] is not None else Decimal('-1'), p['target'].id),
    'profit': lambda p: (p['economics']['profit'] if p.get('economics') else Decimal('-1e18'), p['target'].id),
    'name': lambda p: (p['target'].name.lower(), p['target'].id),
    'scope': lambda p: (scope_label(p['target']).lower(), p['target'].id),
}


def initials(text):
    """Two-letter avatar text, e.g. 'Usama Arif Sial' -> 'US'."""
    words = [w for w in (text or '').split() if w[:1].isalnum()]
    if not words:
        return '?'
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


def items_label(target):
    """'All sales' or the chosen finished items, for lists and headers."""
    if not target.has_item_scope:
        return 'All items'
    names = [p.product.name for p in target.products if p.product]
    if target.removed_product_count:
        names.append(f'{target.removed_product_count} removed item(s)')
    return ', '.join(names)


def scope_label(target):
    if target.target_type == SalesTarget.TYPE_COMPANY:
        return 'Whole company'
    if target.target_type == SalesTarget.TYPE_INDIVIDUAL:
        return target.salesman.name if target.salesman else 'Salesman removed'
    names = [m.salesman.name for m in target.members if m.salesman]
    if not names:
        return 'No members'
    return ', '.join(names)
