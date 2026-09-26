"""Inventory > Warehouse Transfers.

Moves item quantity from one warehouse to another. Stock lives per
warehouse in ProductWarehouseStock; a transfer takes each line's quantity
out of the source row and adds it to the destination row. Product.quantity
(the item's total across every warehouse) is never touched - stock only
changes location.

  * create  -> apply the lines
  * edit    -> reverse the old lines, apply the new ones
  * delete  -> reverse the lines

Every change is validated AFTER it's applied: if any touched warehouse row
would go negative (e.g. the destination already used/sold the stock that a
delete or edit wants to take back) the whole request is rolled back and the
user is told exactly which item/warehouse is short.
"""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, func

from app import db
from app.models import (Company, Product, ProductWarehouseStock, Warehouse,
                        WarehouseTransfer, WarehouseTransferItem)
from app.utils import permission_required, log_activity

bp = Blueprint('warehouse_transfer', __name__)

QTY_EPS = 1e-9


# ── Stock helpers ────────────────────────────────────────────────────────

def _materialize_legacy_stock(product):
    """A product that has never had a ProductWarehouseStock row keeps all
    its stock implicitly in Product.warehouse_id (the legacy single
    warehouse). Turn that into a real row first, so moving stock in or out
    of it can't silently lose the implicit quantity."""
    has_rows = ProductWarehouseStock.query.filter_by(product_id=product.id).first() is not None
    if not has_rows and product.warehouse_id and (product.quantity or 0) > 0:
        db.session.add(ProductWarehouseStock(product_id=product.id,
                                             warehouse_id=product.warehouse_id,
                                             quantity=product.quantity))
        db.session.flush()


def _stock_row(product_id, warehouse_id):
    row = ProductWarehouseStock.query.filter_by(product_id=product_id, warehouse_id=warehouse_id).first()
    if not row:
        row = ProductWarehouseStock(product_id=product_id, warehouse_id=warehouse_id, quantity=0)
        db.session.add(row)
        db.session.flush()
    return row


def warehouse_available_qty(product, warehouse_id):
    """Quantity of `product` currently sitting in `warehouse_id`, including
    the legacy Product.warehouse_id case (see _materialize_legacy_stock)."""
    row = ProductWarehouseStock.query.filter_by(product_id=product.id, warehouse_id=warehouse_id).first()
    if row:
        return float(row.quantity or 0)
    has_rows = ProductWarehouseStock.query.filter_by(product_id=product.id).first() is not None
    if not has_rows and product.warehouse_id == warehouse_id:
        return float(product.quantity or 0)
    return 0.0


def _move_lines(from_wh_id, to_wh_id, lines, direction=1):
    """Apply (direction=1) or reverse (direction=-1) transfer lines.
    lines: iterable of (product, qty). Returns the set of (product_id,
    warehouse_id) rows touched, for validation."""
    touched = set()
    for product, qty in lines:
        _materialize_legacy_stock(product)
        src = _stock_row(product.id, from_wh_id)
        dst = _stock_row(product.id, to_wh_id)
        src.quantity = round((src.quantity or 0) - direction * qty, 6)
        dst.quantity = round((dst.quantity or 0) + direction * qty, 6)
        touched.add((product.id, from_wh_id))
        touched.add((product.id, to_wh_id))
    db.session.flush()
    return touched


def _shortages(touched):
    """Human-readable problems for any touched warehouse row now below 0."""
    problems = []
    for product_id, wh_id in touched:
        row = ProductWarehouseStock.query.filter_by(product_id=product_id, warehouse_id=wh_id).first()
        if row and (row.quantity or 0) < -QTY_EPS:
            product = Product.query.get(product_id)
            wh = Warehouse.query.get(wh_id)
            problems.append(f'{product.name} (SKU: {product.sku}) — short by '
                            f'{abs(row.quantity):g} in {wh.name}')
    return problems


def _next_transfer_number():
    last_id = db.session.query(func.max(WarehouseTransfer.id)).scalar() or 0
    n = last_id + 1
    while True:
        number = f'WT-{n:04d}'
        if not WarehouseTransfer.query.filter_by(transfer_number=number).first():
            return number
        n += 1


def _lines_text(lines):
    return '; '.join(f'{p.name} (SKU: {p.sku}) x {q:g}' for p, q in lines)


def _parse_form():
    """Returns (data dict, lines [(product, qty)], errors [])."""
    errors = []
    try:
        date = datetime.strptime(request.form.get('date', ''), '%Y-%m-%d').date()
    except ValueError:
        date = None
        errors.append('Please enter a valid transfer date.')

    from_id = request.form.get('from_warehouse_id', type=int)
    to_id = request.form.get('to_warehouse_id', type=int)
    from_wh = Warehouse.query.get(from_id) if from_id else None
    to_wh = Warehouse.query.get(to_id) if to_id else None
    if not from_wh:
        errors.append('Select the warehouse to transfer FROM.')
    if not to_wh:
        errors.append('Select the warehouse to transfer TO.')
    if from_wh and to_wh and from_wh.id == to_wh.id:
        errors.append('The source and destination warehouse must be different.')

    merged = {}  # product_id -> qty (same item on two lines is merged)
    for pid, qty in zip(request.form.getlist('product_id[]'), request.form.getlist('quantity[]')):
        if not pid:
            continue
        try:
            q = float(qty)
        except (TypeError, ValueError):
            q = 0
        if q <= 0:
            errors.append('Every item line needs a quantity greater than 0.')
            continue
        merged[int(pid)] = merged.get(int(pid), 0) + q

    lines = []
    for pid, q in merged.items():
        product = Product.query.get(pid)
        if product:
            lines.append((product, round(q, 6)))
    if not lines and not errors:
        errors.append('Add at least one item to transfer.')

    data = {
        'date': date,
        'from_wh': from_wh,
        'to_wh': to_wh,
        'reference': (request.form.get('reference') or '').strip() or None,
        'notes': (request.form.get('notes') or '').strip() or None,
    }
    return data, lines, sorted(set(errors), key=errors.index)


def _date_format():
    company = Company.query.first()
    return company.date_format if company and company.date_format else '%Y-%m-%d'


def _form_context(transfer=None, form_values=None):
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    if transfer:  # keep an inactive warehouse selectable on an old transfer
        for wh in (transfer.from_warehouse, transfer.to_warehouse):
            if wh and wh not in warehouses:
                warehouses.append(wh)
    return dict(transfer=transfer, is_edit=transfer is not None, warehouses=warehouses, form_values=form_values,
                next_number=transfer.transfer_number if transfer else _next_transfer_number(),
                today=datetime.utcnow().date().strftime('%Y-%m-%d'))


def _posted_values():
    """Echo back what the user typed after a validation error."""
    rows = []
    for pid, qty in zip(request.form.getlist('product_id[]'), request.form.getlist('quantity[]')):
        if pid:
            p = Product.query.get(int(pid))
            if p:
                rows.append({'product_id': p.id, 'label': f'{p.name} ({p.sku})', 'quantity': qty,
                             'unit': p.unit or ''})
    return {
        'date': request.form.get('date'),
        'from_warehouse_id': request.form.get('from_warehouse_id', type=int),
        'to_warehouse_id': request.form.get('to_warehouse_id', type=int),
        'reference': request.form.get('reference', ''),
        'notes': request.form.get('notes', ''),
        'items': rows,
    }


# ── Pages ────────────────────────────────────────────────────────────────

@bp.route('/')
@login_required
@permission_required('warehouse', action='view')
def transfers():
    q = WarehouseTransfer.query
    search = (request.args.get('search') or '').strip()
    from_id = request.args.get('from_warehouse_id', type=int)
    to_id = request.args.get('to_warehouse_id', type=int)
    date_from = request.args.get('date_from') or ''
    date_to = request.args.get('date_to') or ''

    if search:
        like = f'%{search}%'
        q = q.filter(or_(
            WarehouseTransfer.transfer_number.ilike(like),
            WarehouseTransfer.reference.ilike(like),
            WarehouseTransfer.notes.ilike(like),
            WarehouseTransfer.items.any(WarehouseTransferItem.product.has(
                or_(Product.name.ilike(like), Product.sku.ilike(like))))
        ))
    if from_id:
        q = q.filter(WarehouseTransfer.from_warehouse_id == from_id)
    if to_id:
        q = q.filter(WarehouseTransfer.to_warehouse_id == to_id)
    try:
        if date_from:
            q = q.filter(WarehouseTransfer.date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        if date_to:
            q = q.filter(WarehouseTransfer.date <= datetime.strptime(date_to, '%Y-%m-%d').date())
    except ValueError:
        flash('Invalid date filter ignored.', 'warning')

    transfer_list = q.order_by(WarehouseTransfer.date.desc(), WarehouseTransfer.id.desc()).all()

    today = datetime.utcnow().date()
    stats = {
        'count': len(transfer_list),
        'this_month': sum(1 for t in transfer_list if t.date and t.date.year == today.year and t.date.month == today.month),
        'total_qty': sum(t.total_quantity for t in transfer_list),
        'total_value': sum(t.total_value for t in transfer_list),
    }
    warehouses = Warehouse.query.order_by(Warehouse.name).all()
    return render_template('inventory/warehouse_transfers.html', transfers=transfer_list, stats=stats,
                           warehouses=warehouses, date_format=_date_format(),
                           filters={'search': search, 'from_warehouse_id': from_id, 'to_warehouse_id': to_id,
                                    'date_from': date_from, 'date_to': date_to})


@bp.route('/new', methods=['GET', 'POST'])
@login_required
@permission_required('warehouse', action='add')
def create_transfer():
    if request.method == 'POST':
        data, lines, errors = _parse_form()
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('inventory/warehouse_transfer_form.html',
                                   **_form_context(form_values=_posted_values()))

        transfer = WarehouseTransfer(
            transfer_number=_next_transfer_number(),
            date=data['date'],
            from_warehouse_id=data['from_wh'].id,
            to_warehouse_id=data['to_wh'].id,
            reference=data['reference'],
            notes=data['notes'],
            created_by=current_user.id,
        )
        for product, qty in lines:
            transfer.items.append(WarehouseTransferItem(product_id=product.id, quantity=qty))
        db.session.add(transfer)

        touched = _move_lines(data['from_wh'].id, data['to_wh'].id, lines, direction=1)
        problems = _shortages(touched)
        if problems:
            db.session.rollback()
            flash('Transfer not saved — not enough stock in the source warehouse:', 'danger')
            for p in problems:
                flash(p, 'danger')
            return render_template('inventory/warehouse_transfer_form.html',
                                   **_form_context(form_values=_posted_values()))

        db.session.commit()
        log_activity('Warehouse', f'Warehouse Transfer {transfer.transfer_number} created',
                     f'{data["from_wh"].name} → {data["to_wh"].name}: {_lines_text(lines)}')
        flash(f'Transfer {transfer.transfer_number} saved — {len(lines)} item(s) moved from '
              f'{data["from_wh"].name} to {data["to_wh"].name}.', 'success')
        return redirect(url_for('warehouse_transfer.transfer_detail', id=transfer.id))

    return render_template('inventory/warehouse_transfer_form.html', **_form_context())


@bp.route('/<int:id>')
@login_required
@permission_required('warehouse', action='view')
def transfer_detail(id):
    transfer = WarehouseTransfer.query.get_or_404(id)
    rows = []
    for item in transfer.items:
        p = item.product
        rows.append({
            'item': item,
            'from_now': warehouse_available_qty(p, transfer.from_warehouse_id) if p else 0,
            'to_now': warehouse_available_qty(p, transfer.to_warehouse_id) if p else 0,
        })
    return render_template('inventory/warehouse_transfer_detail.html', transfer=transfer, rows=rows,
                           date_format=_date_format())


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('warehouse', action='edit')
def edit_transfer(id):
    transfer = WarehouseTransfer.query.get_or_404(id)

    if request.method == 'POST':
        data, lines, errors = _parse_form()
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('inventory/warehouse_transfer_form.html',
                                   **_form_context(transfer, form_values=_posted_values()))

        old_from, old_to = transfer.from_warehouse, transfer.to_warehouse
        old_lines = [(i.product, float(i.quantity or 0)) for i in transfer.items if i.product]

        # 1. Undo the old movement, 2. apply the new one, 3. validate the
        # combined result - so e.g. lowering a quantity only needs the
        # destination to still hold the difference, not the whole amount.
        touched = _move_lines(old_from.id, old_to.id, old_lines, direction=-1)
        touched |= _move_lines(data['from_wh'].id, data['to_wh'].id, lines, direction=1)
        problems = _shortages(touched)
        if problems:
            db.session.rollback()
            flash('Transfer not updated — the change would leave a warehouse with negative stock '
                  '(stock that was moved may already have been used/sold there):', 'danger')
            for p in problems:
                flash(p, 'danger')
            return render_template('inventory/warehouse_transfer_form.html',
                                   **_form_context(transfer, form_values=_posted_values()))

        transfer.date = data['date']
        transfer.from_warehouse_id = data['from_wh'].id
        transfer.to_warehouse_id = data['to_wh'].id
        transfer.reference = data['reference']
        transfer.notes = data['notes']
        transfer.updated_by = current_user.id
        transfer.items.clear()
        for product, qty in lines:
            transfer.items.append(WarehouseTransferItem(product_id=product.id, quantity=qty))

        db.session.commit()
        log_activity('Warehouse', f'Warehouse Transfer {transfer.transfer_number} updated',
                     f'Before: {old_from.name} → {old_to.name}: {_lines_text(old_lines)} | '
                     f'After: {data["from_wh"].name} → {data["to_wh"].name}: {_lines_text(lines)}')
        flash(f'Transfer {transfer.transfer_number} updated — warehouse stock adjusted.', 'success')
        return redirect(url_for('warehouse_transfer.transfer_detail', id=transfer.id))

    return render_template('inventory/warehouse_transfer_form.html', **_form_context(transfer))


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('warehouse', action='delete')
def delete_transfer(id):
    transfer = WarehouseTransfer.query.get_or_404(id)
    number = transfer.transfer_number
    from_wh, to_wh = transfer.from_warehouse, transfer.to_warehouse
    lines = [(i.product, float(i.quantity or 0)) for i in transfer.items if i.product]

    touched = _move_lines(from_wh.id, to_wh.id, lines, direction=-1)
    problems = _shortages(touched)
    if problems:
        db.session.rollback()
        flash(f'Transfer {number} not deleted — {to_wh.name} no longer holds enough of the transferred '
              f'stock to send it back:', 'danger')
        for p in problems:
            flash(p, 'danger')
        return redirect(request.referrer or url_for('warehouse_transfer.transfers'))

    db.session.delete(transfer)
    db.session.commit()
    log_activity('Warehouse', f'Warehouse Transfer {number} deleted (stock reversed)',
                 f'{to_wh.name} → back to {from_wh.name}: {_lines_text(lines)}')
    flash(f'Transfer {number} deleted — stock moved back from {to_wh.name} to {from_wh.name}.', 'success')
    return redirect(url_for('warehouse_transfer.transfers'))


# ── JSON ─────────────────────────────────────────────────────────────────

def _stock_distribution(exclude_transfer_id=None):
    """{product_id: {warehouse_id: qty}} for every item, in 3 queries.
    Includes the legacy Product.warehouse_id case (item with no
    ProductWarehouseStock rows at all). With exclude_transfer_id (edit
    page) that transfer's own movement is undone, so the numbers show what
    each warehouse would hold without it."""
    dist = {}
    for r in ProductWarehouseStock.query.all():
        dist.setdefault(r.product_id, {})[r.warehouse_id] = float(r.quantity or 0)
    for p in Product.query.filter(Product.warehouse_id.isnot(None), Product.quantity > 0).all():
        if p.id not in dist:
            dist[p.id] = {p.warehouse_id: float(p.quantity or 0)}
    if exclude_transfer_id:
        ex = WarehouseTransfer.query.get(exclude_transfer_id)
        if ex:
            for i in ex.items:
                d = dist.setdefault(i.product_id, {})
                d[ex.from_warehouse_id] = d.get(ex.from_warehouse_id, 0) + (i.quantity or 0)
                d[ex.to_warehouse_id] = d.get(ex.to_warehouse_id, 0) - (i.quantity or 0)
    return dist


@bp.route('/api/warehouse-stock')
@login_required
@permission_required('warehouse', action='view')
def warehouse_stock_json():
    """Every active item for the form's item picker, with how much sits in
    each warehouse ('warehouses') and - once a source warehouse is picked -
    how much of it is available there ('available'; None before that).
    Items with no stock in the source are still listed so the user can
    always find what they're looking for; the form shows 0 available and
    blocks transferring more than the source warehouse holds."""
    wh_id = request.args.get('warehouse_id', type=int)
    dist = _stock_distribution(request.args.get('exclude_transfer_id', type=int))
    wh_names = {w.id: w.name for w in Warehouse.query.all()}

    ids_with_stock = [pid for pid, d in dist.items() if any(q > QTY_EPS for q in d.values())]
    products = Product.query.filter(or_(Product.is_active == True, Product.id.in_(ids_with_stock)))         .order_by(Product.name).all()

    results = []
    for p in products:
        d = dist.get(p.id, {})
        breakdown = sorted(
            [{'id': w, 'name': wh_names.get(w, f'Warehouse #{w}'), 'qty': round(q, 4)}
             for w, q in d.items() if q > QTY_EPS],
            key=lambda x: -x['qty'])
        results.append({
            'id': p.id,
            'text': f'{p.name} ({p.sku})',
            'available': round(max(d.get(wh_id, 0), 0), 4) if wh_id else None,
            'unit': p.unit or '',
            'cost_price': float(p.cost_price or 0),
            'unit_price': float(p.unit_price or 0),
            'total_qty': float(p.quantity or 0),
            'warehouses': breakdown,
        })
    return jsonify({'results': results})
