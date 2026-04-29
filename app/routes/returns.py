from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Sale, SaleItem, SaleReturn, SaleReturnItem, Product, Customer, SaleReturnSettings
from app.forms import SaleReturnSettingsForm
from datetime import datetime
from app.routes.filters import apply_saved_filter_to_query

bp = Blueprint('returns', __name__)


@bp.route('/')
@login_required
def return_list():
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    status = request.args.get('status', 'all')

    query = SaleReturn.query

    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
            query = query.filter(SaleReturn.date >= from_date_obj)
        except ValueError:
            pass

    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')
            to_date_obj = to_date_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(SaleReturn.date <= to_date_obj)
        except ValueError:
            pass

    if status != 'all':
        query = query.filter(SaleReturn.status == status)

    query = apply_saved_filter_to_query(query, 'sale_return', request.args)

    returns = query.order_by(SaleReturn.date.desc()).all()

    total_returns = sum(r.total for r in returns)
    total_count = len(returns)

    return render_template('sales/returns.html',
                           returns=returns,
                           from_date=from_date,
                           to_date=to_date,
                           current_status=status,
                           total_returns=total_returns,
                           total_count=total_count,
                           active_module='sale_return',
                           filter_id=request.args.get('filter_id'))


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_return():
    if request.method == 'GET':
        sale_id = request.args.get('sale_id')
        if sale_id:
            sale = Sale.query.get_or_404(int(sale_id))
            return render_template('sales/create_return.html',
                                   sale=sale,
                                   products=Product.query.filter_by(is_active=True).all(),
                                   now=datetime.now())

        sales = Sale.query.order_by(Sale.date.desc()).all()
        return render_template('sales/create_return.html',
                               sales=sales,
                               sale=None,
                               products=Product.query.filter_by(is_active=True).all(),
                               now=datetime.now())

    # POST - process return
    sale_id = request.form.get('sale_id')
    sale = Sale.query.get_or_404(int(sale_id))

    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    prices = request.form.getlist('price[]')

    subtotal = 0
    return_items = []

    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
            product = Product.query.get(int(product_ids[i]))
            quantity = float(quantities[i])
            price = float(prices[i])
            total = quantity * price
            subtotal += total

            return_items.append({
                'product_id': product.id,
                'quantity': quantity,
                'unit_price': price,
                'total': total
            })

    if not return_items:
        flash('Please add at least one item to return.', 'warning')
        return redirect(url_for('returns.create_return', sale_id=sale_id))

    tax_rate = float(request.form.get('tax_rate', 0))
    tax = subtotal * (tax_rate / 100)
    discount = float(request.form.get('discount', 0))
    total = subtotal + tax - discount

    # Generate return number using settings
    settings = SaleReturnSettings.query.first()
    if not settings:
        settings = SaleReturnSettings(return_prefix='RET-', return_suffix='', next_number=1)
        db.session.add(settings)

    # Sync next_number with actual highest return number in DB
    highest_return = SaleReturn.query.order_by(SaleReturn.id.desc()).first()
    if highest_return and highest_return.return_number:
        try:
            prefix_len = len(settings.return_prefix or '')
            suffix_len = len(settings.return_suffix or '')
            num_str = highest_return.return_number[prefix_len:]
            if suffix_len > 0:
                num_str = num_str[:-suffix_len]
            max_num = int(num_str)
            next_return_num = max(settings.next_number, max_num + 1)
        except (ValueError, IndexError):
            next_return_num = settings.next_number
    else:
        next_return_num = settings.next_number

    # Get unique return number
    prefix = settings.return_prefix or ''
    suffix = settings.return_suffix or ''
    while True:
        return_number = f"{prefix}{next_return_num}{suffix}"
        existing = SaleReturn.query.filter_by(return_number=return_number).first()
        if not existing:
            break
        next_return_num += 1

    sale_return = SaleReturn(
        return_number=return_number,
        sale_id=sale.id,
        customer_id=sale.customer_id,
        date=datetime.strptime(request.form.get('date'), '%Y-%m-%d') if request.form.get('date') else datetime.now(),
        subtotal=subtotal,
        tax_rate=tax_rate,
        tax=tax,
        discount=discount,
        total=total,
        reason=request.form.get('reason', ''),
        status='pending',
        returned_to_inventory=False,
        created_by=current_user.id
    )

    db.session.add(sale_return)
    db.session.flush()

    # Create production log for rejected quantities (before returning to inventory)
    return_date = sale_return.date.date() if sale_return.date else datetime.now().date()
    for item in return_items:
        from app.models import ProductionLog
        product = Product.query.get(item['product_id'])
        
        existing_log = ProductionLog.query.filter_by(
            date=return_date,
            sku_id=product.id,
            shift='Sales Return'
        ).first()
        
        if existing_log:
            existing_log.rejected_qty += item['quantity']
            if existing_log.operator and 'Return' not in existing_log.operator:
                existing_log.operator += f", Return: {sale_return.return_number}"
        else:
            production_log = ProductionLog(
                date=return_date,
                sku_id=product.id,
                shift='Sales Return',
                operator=f'Customer: {sale_return.sale.customer.name if sale_return.sale and sale_return.sale.customer else "Unknown"}',
                qty_produced=0,
                rejected_qty=item['quantity'],
                notes=f'Rejected from Return: {sale_return.return_number}',
                created_by=current_user.id
            )
            db.session.add(production_log)

    for item in return_items:
        return_item = SaleReturnItem(
            return_id=sale_return.id,
            product_id=item['product_id'],
            quantity=item['quantity'],
            unit_price=item['unit_price'],
            total=item['total']
        )
        db.session.add(return_item)

    # Update sale totals - reduce sale total by return amount
    sale.subtotal -= subtotal
    sale.tax -= tax
    sale.total -= total
    if sale.total < 0:
        sale.total = 0

    # Adjust paid amount if needed
    if sale.paid_amount > sale.total:
        sale.paid_amount = sale.total

    # Update sale status
    sale.update_status()

    # Update return settings next number
    settings.next_number = next_return_num + 1

    db.session.commit()
    flash(f'Return {return_number} created successfully!', 'success')
    return redirect(url_for('returns.return_detail', id=sale_return.id))


@bp.route('/<int:id>')
@login_required
def return_detail(id):
    sale_return = SaleReturn.query.get_or_404(id)
    return render_template('sales/return_detail.html', sale_return=sale_return)


@bp.route('/<int:id>/return-to-inventory', methods=['POST'])
@login_required
def return_to_inventory(id):
    sale_return = SaleReturn.query.get_or_404(id)
    
    if sale_return.returned_to_inventory:
        flash('This return has already been added back to inventory.', 'warning')
        return redirect(url_for('returns.return_detail', id=id))

    # Update inventory for each item (rejected qty already logged at return creation)
    for item in sale_return.items:
        product = Product.query.get(item.product_id)
        if product:
            product.update_quantity(item.quantity)

    sale_return.returned_to_inventory = True
    sale_return.status = 'completed'
    db.session.commit()

    flash(f'Return {sale_return.return_number} items added back to inventory.', 'success')
    return redirect(url_for('returns.return_detail', id=id))


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_return(id):
    sale_return = SaleReturn.query.get_or_404(id)
    sale = sale_return.sale

    # Reverse inventory changes only if it was already added back
    if sale_return.returned_to_inventory:
        for item in sale_return.items:
            product = Product.query.get(item.product_id)
            if product:
                product.update_quantity(-item.quantity)

    # Delete production log entries for rejected quantities (created at return time)
    return_date = sale_return.date.date() if sale_return.date else None
    for item in sale_return.items:
        if return_date:
            from app.models import ProductionLog
            logs = ProductionLog.query.filter_by(
                date=return_date,
                sku_id=item.product_id,
                shift='Sales Return'
            ).all()
            for log in logs:
                if log.notes and sale_return.return_number in log.notes:
                    db.session.delete(log)
                elif log.rejected_qty >= item.quantity:
                    log.rejected_qty -= item.quantity
                    if log.rejected_qty <= 0:
                        db.session.delete(log)

    # Restore sale totals
    sale.subtotal += sale_return.subtotal
    sale.tax += sale_return.tax
    sale.total += sale_return.total
    sale.update_status()

    db.session.delete(sale_return)
    db.session.commit()
    flash('Return deleted successfully. Sale totals have been restored.', 'success')
    return redirect(url_for('returns.return_list'))


@bp.route('/api/sale/<int:sale_id>')
@login_required
def get_sale_details(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    items = []
    for item in sale.items:
        items.append({
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product.name if item.product else 'Unknown',
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total': item.total
        })
    return jsonify({
        'id': sale.id,
        'invoice_number': sale.invoice_number,
        'customer_name': sale.customer.name if sale.customer else 'Walk-in Customer',
        'tax_rate': sale.tax_rate,
        'items': items
    })

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def sale_return_settings():
    settings = SaleReturnSettings.query.first()
    form = SaleReturnSettingsForm(obj=settings)
    if form.validate_on_submit():
        if not settings:
            settings = SaleReturnSettings()
            db.session.add(settings)
        settings.return_prefix = form.return_prefix.data or 'RET-'
        settings.return_suffix = form.return_suffix.data or ''
        settings.next_number = form.next_number.data or 1
        db.session.commit()
        flash('Sale return settings updated successfully.', 'success')
        return redirect(url_for('returns.sale_return_settings'))
    return render_template('sales/sale_return_settings.html', settings=settings, form=form)
