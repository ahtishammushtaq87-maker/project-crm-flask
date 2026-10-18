"""Targets split into months or quarters, and bulk targets (one per item).

Create form, besides the classic single target:
  * period_mode=yearly  one total amount per row, divided into months
                        (plan_split=month) or quarters (quarter), counting
                        plan_count of them from plan_start_month (all = a
                        full year: 12 months / 4 quarters). Each period becomes
                        an ordinary SalesTarget, linked to a SalesTargetPlan
                        so the split can be edited together.
  * split_items=1       a separate target (row) for every selected item, each
                        with its own amount. Works for a single period too.

Grid fields posted by the form (``key`` is ``all`` or ``p<product id>`` on
create, ``r<row_no>`` on plan edit):
    total_<key>       total amount of the row (yearly mode)
    amt_<key>_<n>     amount of period n (1-12 / 1-4, or 1 for single period)
A period may be 0 (no target then, nothing is created); the periods must add
up exactly to the total. The browser keeps them in
step (static/sales_target/sales_target.js), and the server re-checks it.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from werkzeug.datastructures import MultiDict

from app import db
from app.models import Product
from app.sales_target import calculations as calc
from app.sales_target import services as svc
from app.sales_target.models import SalesTarget, SalesTargetPlan, SalesTargetPlanPart, SalesTargetProduct

MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December')
MAX_SPLIT_ITEMS = 100
CENT = Decimal('0.01')


# ── Periods ────────────────────────────────────────────────────────────────

def _add_months(d, months):
    m = d.month - 1 + months
    return date(d.year + m // 12, m % 12 + 1, 1)


def full_count(months_each):
    return 12 // months_each


def periods(year, start_month=1, months_each=1, count=None):
    """``count`` months (months_each=1) or quarters (3) from ``start_month``
    of ``year``; count=None means a full year (12 months / 4 quarters).
    ``label``/``range`` head the grid columns; ``title`` goes into target
    names and messages."""
    out = []
    start = date(year, start_month, 1)
    for n in range(1, (count or full_count(months_each)) + 1):
        end = _add_months(start, months_each) - timedelta(days=1)
        if months_each == 1:
            label, rng = start.strftime('%b'), start.strftime('%Y')
            title = start.strftime('%b %Y')
        else:
            rng = (f'{start.strftime("%b")}–{end.strftime("%b %Y")}' if start.year == end.year
                   else f'{start.strftime("%b %Y")}–{end.strftime("%b %Y")}')
            label, title = f'Q{n}', f'Q{n} ({rng})'
        out.append({'no': n, 'label': label, 'range': rng, 'title': title, 'start': start, 'end': end})
        start = end + timedelta(days=1)
    return out


def quarters(year, start_month=1):
    return periods(year, start_month, 3)


def plan_periods(plan):
    return periods(plan.year, plan.start_month, plan.period_months or 3, plan.period_count)


def unit_words(plan=None, months_each=None):
    """('month', 'months') for monthly plans, ('quarter', 'quarters') else."""
    if plan is not None:
        months_each = plan.period_months
    return ('month', 'months') if months_each in (None, 1) else ('quarter', 'quarters')


def plan_span_label(plan):
    """'2026' / 'FY 2026-27' for a full year, else 'Jul 2026 – Sep 2026'."""
    if not plan.period_count or plan.period_count == full_count(plan.period_months or 3):
        return year_label(plan.year, plan.start_month)
    ps = plan_periods(plan)
    return f'{ps[0]["start"].strftime("%b %Y")} – {ps[-1]["end"].strftime("%b %Y")}'


def year_label(year, start_month=1):
    return str(year) if start_month == 1 else f'FY {year}-{str(year + 1)[-2:]}'


def year_choices(today=None):
    today = today or date.today()
    return list(range(today.year - 1, today.year + 4))


def split_equal(total, n):
    """Divide ``total`` into ``n`` cent amounts; leftover cents go last."""
    total = Decimal(total).quantize(CENT)
    if n <= 0:
        return []
    cents = int(total * 100)
    base, extra = divmod(cents, n)
    parts = [Decimal(base) / 100] * n
    parts[-1] = Decimal(base + extra) / 100
    return [p.quantize(CENT) for p in parts]


# ── Create ─────────────────────────────────────────────────────────────────

def is_bulk_request(form):
    return form.get('period_mode') == 'yearly' or form.get('split_items') == '1'


def _money(raw, errors, field, label, allow_zero):
    local = {}
    value = svc._parse_money(raw, field, local)
    if field in local:
        errors[field] = f'{label}: {local[field]}'
        return None
    if value < 0 or (value == 0 and not allow_zero):
        errors[field] = f'{label}: must be {"zero or more" if allow_zero else "greater than zero"}.'
        return None
    return value


def _check_row(key, label, form, columns, yearly, errors, units='months'):
    """Validate one grid row; returns (total, [amount per column]) or None."""
    cells = []
    for col in columns:
        col_label = f'{label} – {col["title"]}' if yearly else label
        cells.append(_money(form.get(f'amt_{key}_{col["no"]}'), errors, f'amt_{key}_{col["no"]}',
                            col_label, allow_zero=yearly))
    if not yearly:
        return (cells[0], cells) if cells[0] is not None else None
    total = _money(form.get(f'total_{key}'), errors, f'total_{key}', f'{label} – total target',
                   allow_zero=False)
    if total is None or any(c is None for c in cells):
        return None
    if sum(cells) != total:
        diff = sum(cells) - total
        errors[f'total_{key}'] = (f'{label}: the {units} add up to PKR {sum(cells):,.2f} but the total '
                                  f'target is PKR {total:,.2f} ({"over" if diff > 0 else "short"} by '
                                  f'PKR {abs(diff):,.2f}).')
        return None
    return total, cells


def validate_create(form, today=None):
    """Return (plan_data, errors, grid_errors) for a yearly or bulk create.
    errors use the normal form field names; grid_errors map grid input names
    to messages (shown next to the grid)."""
    today = today or date.today()
    yearly = form.get('period_mode') == 'yearly'
    split = form.get('split_items') == '1'
    errors, grid_errors = {}, {}

    year = start_month = None
    months_each, period_count = 1, None
    if yearly:
        year = svc._parse_int(form.get('plan_year'))
        start_month = svc._parse_int(form.get('plan_start_month')) or 1
        if not year or not (2000 <= year <= 2099):
            errors['plan_year'] = 'Choose the year.'
        if not (1 <= start_month <= 12):
            errors['plan_start_month'] = 'Choose the month it starts in.'
            start_month = 1
        months_each = 3 if form.get('plan_split') == 'quarter' else 1
        period_count = svc._parse_int(form.get('plan_count')) or full_count(months_each)
        if not (1 <= period_count <= full_count(months_each)):
            errors['plan_count'] = f'Choose between 1 and {full_count(months_each)}.'
            period_count = full_count(months_each)
    units = unit_words(months_each=months_each)[1]

    # Shared fields (name, status, salesman, items, notes, bonus) go through
    # the normal target validation, over the whole period, without its
    # duplicate check (each target is checked below).
    base_form = MultiDict(form)
    if yearly and year:
        ps = periods(year, start_month, months_each, period_count)
        base_form['start_date'], base_form['end_date'] = ps[0]['start'].isoformat(), ps[-1]['end'].isoformat()
        columns = ps
    else:
        columns = None
    base_form['target_amount'] = '1'  # amounts are checked in the grid
    base, base_errors = svc.validate_target_form(base_form, today=today, check_duplicate=False)
    errors.update(base_errors)
    if columns is None and not yearly:
        if base.get('start_date') and base.get('end_date'):
            columns = [{'no': 1, 'label': 'Amount', 'range': '', 'title': 'Amount', 'start': base['start_date'],
                        'end': base['end_date']}]

    # Rows: one per item when splitting, else one combined row.
    rows = []
    pids = base.get('product_ids') or []
    if split:
        if not pids and 'product_ids' not in errors:
            errors['product_ids'] = 'Choose the finished items to create a separate target for.'
        elif len(pids) > MAX_SPLIT_ITEMS:
            errors['product_ids'] = f'Choose at most {MAX_SPLIT_ITEMS} items for separate targets.'
        names = {p.id: p.name for p in Product.query.filter(Product.id.in_(pids)).all()} if pids else {}
        rows = [{'key': f'p{pid}', 'product_ids': [pid], 'label': names.get(pid, f'Item #{pid}')}
                for pid in pids]
    else:
        rows = [{'key': 'all', 'product_ids': pids,
                 'label': 'Selected items' if pids else 'All items'}]

    if columns:
        for row in rows:
            checked = _check_row(row['key'], row['label'], form, columns, yearly, grid_errors, units)
            if checked:
                row['total'], row['cells'] = checked
    if grid_errors and '__all__' not in errors:
        errors['grid'] = 'Check the target amounts: ' + next(iter(grid_errors.values()))

    data = {'base': base, 'yearly': yearly, 'split': split, 'year': year, 'start_month': start_month,
            'period_months': months_each,
            'period_count': None if period_count == full_count(months_each) else period_count,
            'columns': columns or [], 'rows': rows}
    if errors:
        return data, errors, grid_errors

    count = sum(1 for r in rows for c in r['cells'] if c > 0)
    if count == 0:
        errors['grid'] = 'Enter at least one target amount.'
        return data, errors, grid_errors
    data['count'] = count

    # Duplicates: same salesman, items and exact dates as an existing target.
    for row in rows:
        for col, amount in zip(columns, row['cells']):
            if amount <= 0:
                continue
            probe = dict(base, start_date=col['start'], end_date=col['end'], product_ids=row['product_ids'])
            dup = svc.find_duplicate(probe)
            if dup:
                errors['__all__'] = (f'A target for {row["label"]}'
                                     f'{" in " + col["title"] if yearly else ""} '
                                     f'already exists: "{dup.name}". Edit that target, or leave this one at 0.')
                return data, errors, grid_errors
    return data, errors, grid_errors


def _target_name(base_name, row, col, data):
    parts = []
    if data['split']:
        parts.append(row['label'])
    if data['yearly']:
        parts.append(col['title'])
    suffix = ' · ' + ' · '.join(parts) if parts else ''
    room = 150 - len(suffix)
    if room < 20:  # very long item name: shorten it instead of the target name
        suffix = suffix[:150 - min(len(base_name), 60) - 1] + '…'
        room = 150 - len(suffix)
    name = base_name if len(base_name) <= room else base_name[:room - 1] + '…'
    return name + suffix


def create(data, user_id):
    """Add the plan (yearly) and its targets to the session. The caller
    commits. Returns (plan or None, [targets])."""
    base = data['base']
    plan = None
    if data['yearly']:
        plan = SalesTargetPlan(name=base['name'], year=data['year'], start_month=data['start_month'],
                               split_by_item=data['split'], period_months=data['period_months'],
                               period_count=data['period_count'], created_by=user_id)
        db.session.add(plan)
    created = []
    now = datetime.utcnow()
    for row_no, row in enumerate(data['rows']):
        for col, amount in zip(data['columns'], row['cells']):
            if amount <= 0:
                continue
            t = SalesTarget(
                name=_target_name(base['name'], row, col, data), target_type=base['target_type'],
                target_amount=float(amount),
                bonus_amount=float(base['bonus_amount']) if base['bonus_amount'] is not None else None,
                start_date=col['start'], end_date=col['end'], salesman_id=base['salesman_id'],
                status=base['status'], description=base['description'],
                created_by=user_id, updated_by=user_id, created_at=now, updated_at=now)
            for pid in row['product_ids']:
                t.products.append(SalesTargetProduct(product_id=pid))
            if plan is not None:
                t.plan_part = SalesTargetPlanPart(plan=plan, row_no=row_no, period_no=col['no'])
            db.session.add(t)
            created.append(t)
    return plan, created


def grid_state(form):
    """Posted grid values, to refill the grid after a validation error."""
    return {k: v for k, v in form.items() if k.startswith(('total_', 'amt_'))}


# ── Existing plans ─────────────────────────────────────────────────────────

def plan_layout(plan):
    """Rows x months (or quarters) of a plan, for its page and edit form."""
    qs = plan_periods(plan)
    by_row = {}
    for part in plan.parts:
        if part.target is not None:
            by_row.setdefault(part.row_no, {})[part.period_no] = part.target
    rows = []
    for row_no in sorted(by_row):
        cells = [by_row[row_no].get(q['no']) for q in qs]
        first = next(t for t in cells if t)
        if plan.split_by_item:
            label = svc.items_label(first)
        else:
            label = svc.items_label(first) if first.has_item_scope else 'All items'
        rows.append({'row_no': row_no, 'key': f'r{row_no}', 'label': label, 'targets': cells})
    return qs, rows


def plan_targets(plan):
    return [p.target for p in plan.parts if p.target is not None]


def plan_performance(plan, today=None):
    """Achievement per month, per row, per month column and overall."""
    qs, rows = plan_layout(plan)
    zero = Decimal('0.00')

    def blank():
        return {'target': zero, 'actual': zero, 'ok': True}

    col_tot = [blank() for _ in qs]
    grand = blank()
    for row in rows:
        row['perfs'] = []
        row_tot = blank()
        for i, t in enumerate(row['targets']):
            perf = calc.performance(t, today=today) if t else None
            row['perfs'].append(perf)
            if not perf or t.status not in SalesTarget.COUNTED_STATUSES:
                continue
            for agg in (row_tot, col_tot[i], grand):
                agg['target'] += perf['target_amount']
                if perf['available']:
                    agg['actual'] += perf['actual']
                else:
                    agg['ok'] = False
        row['total'] = _finish(row_tot)
    return {'periods': qs, 'rows': rows, 'columns': [_finish(c) for c in col_tot], 'grand': _finish(grand)}


def _finish(agg):
    agg['achievement'] = ((agg['actual'] / agg['target'] * 100).quantize(Decimal('0.1'))
                          if agg['ok'] and agg['target'] > 0 else None)
    return agg


def validate_plan_edit(plan, form):
    """Return ({target: new amount}, errors). Completed/cancelled months
    keep their amount but still count toward the yearly total."""
    qs, rows = plan_layout(plan)
    units = unit_words(plan)[1]
    errors, updates = {}, {}
    for row in rows:
        label = row['label']
        total = _money(form.get(f'total_{row["key"]}'), errors, f'total_{row["key"]}',
                       f'{label} – total target', allow_zero=False)
        running = Decimal('0.00')
        complete = total is not None
        for q, t in zip(qs, row['targets']):
            if t is None:
                continue
            if t.is_closed:
                running += calc.to_money(t.target_amount)
                continue
            field = f'amt_{row["key"]}_{q["no"]}'
            amount = _money(form.get(field), errors, field, f'{label} – {q["title"]}', allow_zero=False)
            if amount is None:
                complete = False
                continue
            running += amount
            updates[t] = amount
        if complete and running != total:
            diff = running - total
            errors[f'total_{row["key"]}'] = (
                f'{label}: the {units} add up to PKR {running:,.2f} but the total target is '
                f'PKR {total:,.2f} ({"over" if diff > 0 else "short"} by PKR {abs(diff):,.2f}).')
    return updates, errors
