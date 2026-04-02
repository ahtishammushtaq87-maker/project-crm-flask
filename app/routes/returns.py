from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Sale, SaleItem, SaleReturn, SaleReturnItem, Product, Customer
from datetime import datetime

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

    returns = query.order_by(SaleReturn.date.desc()).all()

    total_returns = sum(r.total for r in returns)
    total_count = len(returns)

    return render_template('sales/returns.html',
                           returns=returns,
                           from_date=from_date,
                           to_date=to_date,
                           current_status=status,
                           total_returns=total_returns,
                           total_count=total_count)


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

    # Generate return number
    last_return = SaleReturn.query.order_by(SaleReturn.id.desc()).first()
    return_number = f"RET-{datetime.now().strftime('%Y%m')}-{(last_return.id + 1) if last_return else 1:04d}"

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
        status='completed',
        created_by=current_user.id
    )

    db.session.add(sale_return)
    db.session.flush()

    for item in return_items:
        return_item = SaleReturnItem(
            return_id=sale_return.id,
            product_id=item['product_id'],
            quantity=item['quantity'],
            unit_price=item['unit_price'],
            total=item['total']
        )
        db.session.add(return_item)

        # Restore inventory
        product = Product.query.get(item['product_id'])
        product.update_quantity(item['quantity'])

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

    db.session.commit()
    flash(f'Return {return_number} created successfully!', 'success')
    return redirect(url_for('returns.return_detail', id=sale_return.id))


@bp.route('/<int:id>')
@login_required
def return_detail(id):
    sale_return = SaleReturn.query.get_or_404(id)
    return render_template('sales/return_detail.html', sale_return=sale_return)


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_return(id):
    sale_return = SaleReturn.query.get_or_404(id)
    sale = sale_return.sale

    # Reverse inventory changes
    for item in sale_return.items:
        product = Product.query.get(item.product_id)
        if product:
            product.update_quantity(-item.quantity)

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
