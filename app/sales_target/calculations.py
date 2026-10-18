"""Actual-sales calculation for Sales Targets.

Read-only: nothing here writes to invoices, returns or payments.

What counts as a sale
---------------------
The same rule the Dashboard's "Total Sales" card uses
(app/routes/dashboard.py): an invoice counts once it is admin-approved and not
rejected. A cancelled invoice is stored as is_rejected=True (reason
'Cancelled by Admin'; the status enum has no 'cancelled' value), so the
is_rejected filter removes it. Drafts are excluded explicitly as well;
saving a draft clears is_approved already, so this only guards older rows.

The amount used is ``sales.total``, the invoice grand total after line
discounts, invoice discount, tax and delivery. Approving a sales return
re-runs Sale.calculate_totals(), which deducts the return from that same
invoice's total, so returns are already reflected and are deliberately
not subtracted a second time. A return therefore reduces the invoice it
belongs to, in that invoice's period and for that invoice's salesman, even if
the return itself is dated later.

Item-scoped targets (limited to chosen finished items) are measured on
invoice lines instead: for each eligible invoice, the selected items' line
amount after line discount (sale_items.total - discount), minus the same
items' lines on approved returns of that invoice (sale_return_items.total -
discount, the return's prorated share of the line discount). Invoice-level
tax, delivery and invoice discount can't be split per item, so they are not
part of an item target. Returns stay attributed to the original invoice, as
for whole-invoice targets.

Payments are never counted: they settle an invoice that was already counted.
Each invoice is one row in ``sales``, so summing it can't double-count.

Period: an invoice belongs to a target when its invoice date falls on any day
from start_date to end_date inclusive.

Attribution: ``sales.salesman_id`` (one salesman per invoice). Team targets
use ``salesman_id IN (members)``, so overlapping membership can never count an
invoice twice. Invoices without a salesman only count toward company-wide
targets; nothing is ever attributed to the logged-in user.

Cost, selling price and profit (economics())
--------------------------------------------
Measured on the invoice lines of the counted invoices (only the target's items
for an item-scoped target), the same way the invoice form shows line profit:
  selling price = line amount after line discount, minus the same item's lines
                  on approved returns of that invoice
  cost          = unit cost x quantity sold, minus the returned quantity's cost
  profit        = selling price - cost;  margin = profit / selling price
Unit cost is the cost of the warehouse the line was sold from, falling back to
the item's normal cost (services/warehouse_cost.py, as the Dashboard and COGS
report use). It is the item's current cost: invoice lines don't store a
historical cost. Invoice-level tax, delivery and invoice discount belong to no
item, so for a whole-invoice target Actual Sales = selling price + those
invoice charges (shown as ``invoice_charges``).
"""
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select

from app import db
from app.models import Sale, SaleItem, SaleReturn, SaleReturnItem, Customer, Salesman, Product
from app.sales_target.models import SalesTarget
from app.services import warehouse_cost

CENT = Decimal('0.01')


def to_money(value):
    """Float/None/str -> Decimal rounded to cents (str() avoids binary noise)."""
    if value is None:
        return Decimal('0.00')
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def eligible_sale_conditions():
    """Invoice eligibility, mirroring the Dashboard 'Total Sales' filter."""
    return [
        Sale.is_approved == True,  # noqa: E712
        Sale.is_rejected == False,  # noqa: E712
        Sale.is_draft == False,  # noqa: E712
        Sale.status != 'cancelled',
    ]


def period_conditions(start_date, end_date):
    """Invoice date within [start_date, end_date] inclusive. sales.date is a
    DATETIME, so the end bound is midnight after end_date (no 23:59:59 gap)."""
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    return [Sale.date >= start_dt, Sale.date < end_dt]


class ScopeUnavailable(Exception):
    """The target's scope can't be resolved (e.g. its salesman was deleted),
    so no figure is shown instead of a misleading zero."""


def scope_conditions(target):
    if target.target_type == SalesTarget.TYPE_COMPANY:
        return []
    if target.target_type == SalesTarget.TYPE_INDIVIDUAL:
        if target.salesman_id is None:
            raise ScopeUnavailable('The salesman assigned to this target no longer exists. '
                                   'Edit the target and assign a salesman.')
        return [Sale.salesman_id == target.salesman_id]
    if target.target_type == SalesTarget.TYPE_TEAM:
        ids = target.member_ids
        if not ids:
            raise ScopeUnavailable('This team target has no salesmen (they may have been deleted). '
                                   'Edit the target and choose its team members.')
        return [Sale.salesman_id.in_(ids)]
    raise ScopeUnavailable(f'Unknown target type "{target.target_type}".')


def _check_items(target):
    if target.has_item_scope and not target.product_ids:
        raise ScopeUnavailable('The finished items this target was set for no longer exist. '
                               'Edit the target and choose its items again.')


def _base_conditions(target):
    """Period + salesman scope (no eligibility). Raises ScopeUnavailable."""
    _check_items(target)
    return period_conditions(target.start_date, target.end_date) + scope_conditions(target)


def _conditions(target):
    return eligible_sale_conditions() + _base_conditions(target)


def _item_subqueries(product_ids):
    """Per-invoice net amount of the chosen items, and of those items on
    approved returns of the invoice."""
    line_net = SaleItem.total - func.coalesce(SaleItem.discount, 0)
    items = (db.session.query(SaleItem.sale_id.label('sale_id'),
                              func.sum(line_net).label('amount'),
                              func.sum(SaleItem.quantity).label('qty'))
             .filter(SaleItem.product_id.in_(product_ids))
             .group_by(SaleItem.sale_id).subquery())
    ret_net = SaleReturnItem.total - func.coalesce(SaleReturnItem.discount, 0)
    returned = (db.session.query(SaleReturn.sale_id.label('sale_id'),
                                 func.sum(ret_net).label('amount'))
                .join(SaleReturnItem, SaleReturnItem.return_id == SaleReturn.id)
                .filter(SaleReturnItem.product_id.in_(product_ids),
                        SaleReturn.is_approved == True,  # noqa: E712
                        SaleReturn.is_rejected == False)  # noqa: E712
                .group_by(SaleReturn.sale_id).subquery())
    return items, returned


def _measure(target, conds):
    """(total, invoice_count) of the invoices matching ``conds``, measured
    the way this target counts sales (whole invoice, or chosen items)."""
    if not target.has_item_scope:
        return db.session.query(func.sum(Sale.total), func.count(Sale.id)).filter(*conds).one()
    items, returned = _item_subqueries(target.product_ids)
    return (db.session.query(func.sum(items.c.amount - func.coalesce(returned.c.amount, 0)),
                             func.count(Sale.id))
            .select_from(Sale)
            .join(items, items.c.sale_id == Sale.id)
            .outerjoin(returned, returned.c.sale_id == Sale.id)
            .filter(*conds).one())


def performance(target, today=None, with_economics=False):
    """All figures for one target. ``available`` is False (and the figures
    None) when the scope can't be resolved. with_economics adds cost, selling
    price and profit totals under ``economics`` (None when unavailable)."""
    today = today or date.today()
    amount = to_money(target.target_amount)
    result = {
        'target': target,
        'target_amount': amount,
        'available': True,
        'error': None,
        'actual': None,
        'invoice_count': 0,
        'remaining': None,
        'exceeded': None,
        'achievement': None,
        'progress': 0,
        'economics': None,
    }
    try:
        conds = _conditions(target)
    except ScopeUnavailable as e:
        result.update(available=False, error=str(e))
    else:
        total, count = _measure(target, conds)
        actual = to_money(total)
        result.update(
            actual=actual,
            invoice_count=int(count or 0),
            remaining=max(amount - actual, Decimal('0.00')),
            exceeded=max(actual - amount, Decimal('0.00')),
            achievement=achievement_pct(actual, amount),
        )
        result['progress'] = float(min(result['achievement'] or 0, Decimal('100')))
        if with_economics:
            result['economics'] = economics(target, actual=actual, conds=conds)

    result.update(timing(target, today))
    result.update(health(result))
    return result


def achievement_pct(actual, amount):
    if amount is None or amount <= 0:
        return None
    return (actual / amount * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


def timing(target, today):
    """Where today sits in the target period, used for pace-based colouring."""
    total_days = (target.end_date - target.start_date).days + 1
    if today < target.start_date:
        state, elapsed = 'upcoming', 0
    elif today > target.end_date:
        state, elapsed = 'ended', total_days
    else:
        state, elapsed = 'running', (today - target.start_date).days + 1
    return {
        'period_state': state,
        'period_days': total_days,
        'elapsed_days': elapsed,
        'days_until_start': max((target.start_date - today).days, 0),
        'elapsed_pct': Decimal(elapsed * 100 / total_days).quantize(Decimal('0.1')) if total_days else Decimal('0'),
    }


def health(perf):
    """green = achieved/on pace, amber = slightly behind pace, red = behind or
    missed. Pace = share of the period already elapsed."""
    t = perf['target']
    if not perf['available']:
        return {'tone': 'muted', 'tone_label': 'Not available'}
    if t.status in ('draft', 'cancelled'):
        return {'tone': 'muted', 'tone_label': t.status_label}
    ach = perf['achievement'] or Decimal('0')
    if ach >= 100:
        return {'tone': 'good', 'tone_label': 'Achieved'}
    state = perf['period_state']
    if state == 'upcoming':
        return {'tone': 'muted', 'tone_label': 'Not started'}
    if state == 'ended':
        return {'tone': 'bad', 'tone_label': 'Missed'}
    pace = perf['elapsed_pct']
    if ach >= pace:
        return {'tone': 'good', 'tone_label': 'On track'}
    if ach >= pace * Decimal('0.8'):
        return {'tone': 'warn', 'tone_label': 'Needs attention'}
    return {'tone': 'bad', 'tone_label': 'Behind'}


def contributing_invoices(target, page=1, per_page=25, restrict_salesman_ids=None):
    """Paginated invoices counted toward ``target`` (same conditions as
    performance(), so the rows always add up to the Actual Sales figure).
    ``restrict_salesman_ids`` narrows the rows a scoped user may see."""
    conds = _conditions(target)
    if restrict_salesman_ids is not None:
        conds.append(Sale.salesman_id.in_(restrict_salesman_ids or [-1]))
    if target.has_item_scope:
        return _item_invoices(target, conds, page, per_page)
    query = (db.session.query(Sale, Customer.name, Salesman.name)
             .outerjoin(Customer, Sale.customer_id == Customer.id)
             .outerjoin(Salesman, Sale.salesman_id == Salesman.id)
             .filter(*conds)
             .order_by(Sale.date.desc(), Sale.id.desc()))
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    ids = [row[0].id for row in pagination.items]
    returns_by_sale = {}
    if ids:
        returns_by_sale = dict(
            db.session.query(SaleReturn.sale_id, func.sum(SaleReturn.total))
            .filter(SaleReturn.sale_id.in_(ids), SaleReturn.is_approved == True)  # noqa: E712
            .group_by(SaleReturn.sale_id).all())

    rows = []
    for sale, customer_name, salesman_name in pagination.items:
        rows.append({
            'sale': sale,
            'customer_name': customer_name,
            'salesman_name': salesman_name,
            'amount': to_money(sale.total),
            'returns': to_money(returns_by_sale.get(sale.id)),
            'qty': None,
        })
    return pagination, rows


def _item_invoices(target, conds, page, per_page):
    items, returned = _item_subqueries(target.product_ids)
    query = (db.session.query(Sale, Customer.name, Salesman.name,
                              items.c.amount, items.c.qty, returned.c.amount)
             .join(items, items.c.sale_id == Sale.id)
             .outerjoin(returned, returned.c.sale_id == Sale.id)
             .outerjoin(Customer, Sale.customer_id == Customer.id)
             .outerjoin(Salesman, Sale.salesman_id == Salesman.id)
             .filter(*conds)
             .order_by(Sale.date.desc(), Sale.id.desc()))
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    rows = []
    for sale, customer_name, salesman_name, amount, qty, ret in pagination.items:
        rows.append({
            'sale': sale,
            'customer_name': customer_name,
            'salesman_name': salesman_name,
            'amount': to_money(amount) - to_money(ret),
            'returns': to_money(ret),
            'qty': qty,
        })
    return pagination, rows


def exclusions(target):
    """Invoices in the target's period and scope that were NOT counted, so the
    detail page can explain the gap instead of hiding it."""
    try:
        base = _base_conditions(target)
    except ScopeUnavailable:
        return {}

    def summary(*extra):
        total, count = _measure(target, base + list(extra))
        return {'count': int(count or 0), 'amount': to_money(total)}

    out = {
        'pending': summary(Sale.is_approved == False, Sale.is_rejected == False,  # noqa: E712
                           Sale.is_draft == False),  # noqa: E712
        'draft': summary(Sale.is_draft == True, Sale.is_rejected == False),  # noqa: E712
        'rejected': summary(Sale.is_rejected == True),  # noqa: E712
    }
    if target.target_type == SalesTarget.TYPE_COMPANY:
        out['unassigned'] = summary(*eligible_sale_conditions(), Sale.salesman_id.is_(None))
    return out


# ── Cost, selling price and profit ─────────────────────────────────────────

def _dec(value):
    return Decimal(str(value)) if value is not None else Decimal('0')


def margin_pct(profit, selling):
    """Profit as a % of selling price; None when nothing was sold."""
    if profit is None or selling is None or selling <= 0:
        return None
    return (profit / selling * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


def _line_rows(target, conds):
    """(sold lines, approved-return lines) of the counted invoices, as plain
    tuples: sale_id, product_id, line warehouse, qty, line total, line
    discount, item name, sku, item warehouse, item cost."""
    counted = select(Sale.id).where(*conds)
    cols = (Product.name, Product.sku, Product.warehouse_id, Product.cost_price)
    sold = (db.session.query(SaleItem.sale_id, SaleItem.product_id, SaleItem.warehouse_id, SaleItem.quantity,
                             SaleItem.total, SaleItem.discount, *cols)
            .outerjoin(Product, Product.id == SaleItem.product_id)
            .filter(SaleItem.sale_id.in_(counted)))
    returned = (db.session.query(SaleReturn.sale_id, SaleReturnItem.product_id, SaleReturnItem.warehouse_id,
                                 SaleReturnItem.quantity, SaleReturnItem.total, SaleReturnItem.discount, *cols)
                .join(SaleReturnItem, SaleReturnItem.return_id == SaleReturn.id)
                .outerjoin(Product, Product.id == SaleReturnItem.product_id)
                .filter(SaleReturn.sale_id.in_(counted),
                        SaleReturn.is_approved == True,  # noqa: E712
                        SaleReturn.is_rejected == False))  # noqa: E712
    if target.has_item_scope:
        sold = sold.filter(SaleItem.product_id.in_(target.product_ids))
        returned = returned.filter(SaleReturnItem.product_id.in_(target.product_ids))
    return sold.all(), returned.all()


def _blank_line(product_id, name, sku):
    return {'product_id': product_id, 'name': name or 'Deleted item', 'sku': sku or '',
            'qty': 0.0, 'returned_qty': 0.0, 'selling': Decimal('0'), 'cost': Decimal('0'),
            'no_cost': False}


def _finish_line(line):
    """Round the running sums to cents and add profit, margin and per-unit
    figures (net of returns)."""
    line['selling'] = line['selling'].quantize(CENT, rounding=ROUND_HALF_UP)
    line['cost'] = line['cost'].quantize(CENT, rounding=ROUND_HALF_UP)
    line['profit'] = line['selling'] - line['cost']
    line['margin'] = margin_pct(line['profit'], line['selling'])
    qty = line['qty']
    line['unit_price'] = (line['selling'] / _dec(qty)).quantize(CENT) if qty > 1e-9 else None
    line['unit_cost'] = (line['cost'] / _dec(qty)).quantize(CENT) if qty > 1e-9 else None
    return line


def _sum_lines(lines):
    selling = sum((ln['selling'] for ln in lines), Decimal('0.00'))
    cost = sum((ln['cost'] for ln in lines), Decimal('0.00'))
    return {'selling': selling, 'cost': cost, 'profit': selling - cost,
            'margin': margin_pct(selling - cost, selling), 'qty': sum(ln['qty'] for ln in lines)}


def economics(target, actual=None, conds=None):
    """Cost, selling price and profit of everything counted toward ``target``:
    totals, per invoice (``by_sale``, with its item lines) and per item
    (``by_item``, best sellers first). See the module notes for the rules.
    Raises ScopeUnavailable like performance() would report it."""
    if conds is None:
        conds = _conditions(target)
    sold, returned = _line_rows(target, conds)
    cmap = warehouse_cost.cost_map({r[1] for r in sold} | {r[1] for r in returned})

    lines = {}  # (sale_id, product_id) -> line; repeated lines of an item merge
    for sign, rows in ((1, sold), (-1, returned)):
        for sale_id, pid, line_wh, qty, total, discount, name, sku, item_wh, item_cost in rows:
            own = cmap.get(pid, {}).get(line_wh or item_wh)
            unit_cost = _dec(own if own is not None else (item_cost or 0))
            line = lines.setdefault((sale_id, pid), _blank_line(pid, name, sku))
            qty = float(qty or 0)
            line['qty'] += sign * qty
            if sign < 0:
                line['returned_qty'] += qty
            line['selling'] += sign * (_dec(total) - _dec(discount))
            line['cost'] += sign * unit_cost * _dec(qty)
            if unit_cost <= 0:
                line['no_cost'] = True

    by_sale, items = {}, {}
    for (sale_id, pid), line in lines.items():
        item = items.setdefault(pid, _blank_line(pid, line['name'], line['sku']))
        for key in ('qty', 'returned_qty', 'selling', 'cost'):
            item[key] += line[key]
        item['no_cost'] = item['no_cost'] or line['no_cost']
        by_sale.setdefault(sale_id, []).append(_finish_line(line))

    sales = {}
    for sale_id, sale_lines in by_sale.items():
        sale_lines.sort(key=lambda ln: (-ln['selling'], ln['name']))
        sales[sale_id] = dict(_sum_lines(sale_lines), lines=sale_lines)

    by_item = sorted((_finish_line(i) for i in items.values()), key=lambda i: (-i['selling'], i['name']))
    out = _sum_lines(by_item)
    for i in by_item:
        i['share'] = ((i['selling'] / out['selling'] * 100).quantize(Decimal('0.1'))
                      if out['selling'] > 0 else None)

    actual = to_money(actual) if actual is not None else to_money(_measure(target, conds)[0])
    amount = to_money(target.target_amount)
    out.update(
        by_sale=sales,
        by_item=by_item,
        # Tax, delivery and invoice discount: in Actual Sales, but on no item.
        invoice_charges=Decimal('0.00') if target.has_item_scope else actual - out['selling'],
        items_without_cost=[i['name'] for i in by_item if i['no_cost']],
        # Profit if the rest of the target sells at the same profit rate.
        profit_at_target=((out['profit'] / actual * amount).quantize(CENT, rounding=ROUND_HALF_UP)
                          if actual > 0 else None),
    )
    return out


def running_achievement(target, conds=None):
    """Achievement after each counted invoice, oldest first:
    {sale_id: (running amount, running %)} plus the id of the invoice that
    took the target to 100% (None if not reached)."""
    if conds is None:
        conds = _conditions(target)
    if target.has_item_scope:
        items, returned = _item_subqueries(target.product_ids)
        query = (db.session.query(Sale.id, items.c.amount - func.coalesce(returned.c.amount, 0))
                 .select_from(Sale)
                 .join(items, items.c.sale_id == Sale.id)
                 .outerjoin(returned, returned.c.sale_id == Sale.id))
    else:
        query = db.session.query(Sale.id, Sale.total)
    amount = to_money(target.target_amount)
    running, out, reached_by = Decimal('0.00'), {}, None
    for sale_id, value in query.filter(*conds).order_by(Sale.date, Sale.id).all():
        running += to_money(value)
        pct = achievement_pct(running, amount)
        out[sale_id] = (running, pct)
        if reached_by is None and pct is not None and pct >= 100:
            reached_by = sale_id
    return out, reached_by


def annotate_invoices(target, rows, econ, running):
    """Add each invoice's share of the target, the achievement after it, and
    its cost / selling price / profit to contributing_invoices() rows."""
    amount = to_money(target.target_amount)
    by_sale = (econ or {}).get('by_sale', {})
    for row in rows:
        sid = row['sale'].id
        row['share'] = achievement_pct(row['amount'], amount)
        row['running'], row['running_pct'] = running.get(sid, (None, None))
        row['econ'] = by_sale.get(sid)
    return rows
