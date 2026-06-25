from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.utils import permission_required
from flask_login import login_required, current_user
from app import db
from app.models import (Sale, SaleItem, SaleReturn, SaleReturnItem, Product, ProductWarehouseStock, Warehouse,
                        Customer, SaleReturnSettings, CustomerGroup, Salesman, CustomerAdvance)
from app.forms import SaleReturnSettingsForm
from datetime import datetime
from app.routes.filters import apply_saved_filter_to_query
from sqlalchemy import or_

bp = Blueprint('returns', __name__)


@bp.route('/')
@login_required
def return_list():
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    return_num = request.args.get('return_number', '') 
    customer_id = request.args.get('customer_id')
    customer_group_id = request.args.get('customer_group_id')
    salesman_id = request.args.get('salesman_id')

    query = SaleReturn.query.join(Sale)

    # Search filter (Return #, original Invoice #, or Customer Name)
    if search:
        search_filter = f"%{search}%"
        query = query.outerjoin(Customer, SaleReturn.customer_id == Customer.id).filter(
            or_(
                SaleReturn.return_number.ilike(search_filter),
                Sale.invoice_number.ilike(search_filter),
                Customer.name.ilike(search_filter)
            )
        )

    if return_num:
        query = query.filter(SaleReturn.return_number == return_num)

    if customer_id:
        query = query.filter(SaleReturn.customer_id == customer_id)

    if customer_group_id:
        # Check if Customer is already joined
        if not any(j.entity == Customer for j in query._join_entities):
            query = query.outerjoin(Customer, SaleReturn.customer_id == Customer.id)
        query = query.filter(Customer.group_id == customer_group_id)

    if salesman_id:
        query = query.filter(Sale.salesman_id == salesman_id)

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

    # Load data for searchable dropdowns
    salesmen = Salesman.query.filter_by(is_active=True).all()
    all_customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    customer_groups = CustomerGroup.query.filter_by(is_active=True).order_by(CustomerGroup.name).all()
    # Limit number of recent returns to 1000
    recent_returns = SaleReturn.query.order_by(SaleReturn.return_number.desc()).limit(1000).all()

    return render_template('sales/returns.html',
                           returns=returns,
                           from_date=from_date,
                           to_date=to_date,
                           current_status=status,
                           search=search,
                           return_number=return_num,
                           customer_id=customer_id,
                           customer_group_id=customer_group_id,
                           salesman_id=salesman_id,
                           salesmen=salesmen,
                           all_customers=all_customers,
                           customer_groups=customer_groups,
                           recent_returns=recent_returns,
                           total_returns=total_returns,
                           total_count=total_count,
                           active_module='sale_return',
                           filter_id=request.args.get('filter_id'))


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('returns', action='add')
def create_return():
    if request.method == 'GET':
        sale_id = request.args.get('sale_id')
        if sale_id:
            sale = Sale.query.get_or_404(int(sale_id))
            warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
            return render_template('sales/create_return.html',
                                   sale=sale,
                                   products=Product.query.filter_by(is_active=True).all(),
                                   warehouses=warehouses,
                                   now=datetime.now())

        sales = Sale.query.order_by(Sale.date.desc()).all()
        warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
        return render_template('sales/create_return.html',
                       sales=sales,
                       sale=None,
                       products=Product.query.filter_by(is_active=True).all(),
                       warehouses=warehouses,
                       now=datetime.now())

    # POST - process return
    sale_id = request.form.get('sale_id')
    sale = Sale.query.get_or_404(int(sale_id))

    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    prices = request.form.getlist('price[]')
    warehouses = request.form.getlist('warehouse_id[]')

    subtotal = 0
    return_items = []

    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
            product = Product.query.get(int(product_ids[i]))
            quantity = float(quantities[i])
            price = float(prices[i])
            total = quantity * price
            subtotal += total

            wh = None
            try:
                wh = int(warehouses[i]) if i < len(warehouses) and warehouses[i] else None
            except Exception:
                wh = None

            return_items.append({
                'product_id': product.id,
                'warehouse_id': wh,
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

    is_admin = getattr(current_user, 'is_admin', False)
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
        status='approved' if is_admin else 'pending',
        is_approved=is_admin,
        approved_by=current_user.id if is_admin else None,
        approved_at=datetime.utcnow() if is_admin else None,
        returned_to_inventory=False,
        created_by=current_user.id
    )

    db.session.add(sale_return)
    db.session.flush()

    if sale_return.is_approved:
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
            warehouse_id=item.get('warehouse_id'),
            quantity=item['quantity'],
            unit_price=item['unit_price'],
            total=item['total']
        )
        db.session.add(return_item)

    # Update sale totals and status if approved
    if sale_return.is_approved:
        sale.calculate_totals()
        sale.update_status()

        # Adjust paid_amount if needed and create advance for excess
        if sale.paid_amount > sale.total:
            excess = sale.paid_amount - sale.total
            
            # Create a customer advance for the excess
            advance = CustomerAdvance(
                customer_id=sale.customer_id,
                amount=excess,
                date=datetime.now().date(),
                description=f"Auto-generated from Return {return_number} excess (Invoice #{sale.invoice_number})",
                is_approved=True,
                created_by=current_user.id
            )
            db.session.add(advance)
            
            # Adjust sale paid_amount to exactly match the new total
            sale.paid_amount = sale.total
            flash(f'Excess payment of PKR {excess:,.2f} has been converted to a customer advance.', 'info')
        elif sale.paid_amount > sale.total: # Fallback safety
            sale.paid_amount = sale.total

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


@bp.route('/<int:id>/approve', methods=['POST'])
@login_required
@permission_required('returns', action='edit')
def approve_return(id):
    if not getattr(current_user, 'is_admin', False):
        flash('Only admins can approve returns.', 'danger')
        return redirect(url_for('returns.return_detail', id=id))
        
    sale_return = SaleReturn.query.get_or_404(id)
    
    if sale_return.is_approved:
        flash('This return is already approved.', 'warning')
        return redirect(url_for('returns.return_detail', id=id))

    # Set approval fields
    sale_return.is_approved = True
    sale_return.is_rejected = False
    sale_return.status = 'approved'
    sale_return.approved_by = current_user.id
    sale_return.approved_at = datetime.utcnow()
    
    # 1. Update sale totals and status
    sale = sale_return.sale
    sale.calculate_totals()
    sale.update_status()

    # 2. Adjust paid_amount if needed and create advance for excess
    if sale.paid_amount > sale.total:
        excess = sale.paid_amount - sale.total
        from app.models import CustomerAdvance
        advance = CustomerAdvance(
            customer_id=sale.customer_id,
            amount=excess,
            date=datetime.now().date(),
            description=f"Auto-generated from Return {sale_return.return_number} excess (Invoice #{sale.invoice_number})",
            is_approved=True,
            created_by=current_user.id
        )
        db.session.add(advance)
        sale.paid_amount = sale.total
        flash(f'Excess payment of PKR {excess:,.2f} has been converted to a customer advance.', 'info')

    # 3. Create production log for rejected quantities
    return_date = sale_return.date.date() if sale_return.date else datetime.now().date()
    for item in sale_return.items:
        from app.models import ProductionLog, Product
        product = Product.query.get(item.product_id)
        
        existing_log = ProductionLog.query.filter_by(
            date=return_date,
            sku_id=product.id,
            shift='Sales Return'
        ).first()
        
        if existing_log:
            existing_log.rejected_qty += item.quantity
            if existing_log.operator and 'Return' not in existing_log.operator:
                existing_log.operator += f", Return: {sale_return.return_number}"
        else:
            production_log = ProductionLog(
                date=return_date,
                sku_id=product.id,
                shift='Sales Return',
                operator=f'Customer: {sale.customer.name if sale.customer else "Unknown"}',
                qty_produced=0,
                rejected_qty=item.quantity,
                notes=f'Rejected from Return: {sale_return.return_number}',
                created_by=current_user.id
            )
            db.session.add(production_log)

    db.session.commit()
    flash(f'Return {sale_return.return_number} approved successfully!', 'success')
    return redirect(url_for('returns.return_detail', id=id))


@bp.route('/<int:id>/reject', methods=['POST'])
@login_required
@permission_required('returns', action='edit')
def reject_return(id):
    if not getattr(current_user, 'is_admin', False):
        flash('Only admins can reject returns.', 'danger')
        return redirect(url_for('returns.return_detail', id=id))

    sale_return = SaleReturn.query.get_or_404(id)
    reason = request.form.get('reason', '')
    
    sale_return.is_approved = False
    sale_return.is_rejected = True
    sale_return.rejection_reason = reason
    sale_return.status = 'rejected'
    
    db.session.commit()
    flash(f'Return {sale_return.return_number} has been rejected.', 'warning')
    return redirect(url_for('returns.return_detail', id=id))


@bp.route('/<int:id>/return-to-inventory', methods=['POST'])
@login_required
@permission_required('returns', action='edit')
def return_to_inventory(id):
    sale_return = SaleReturn.query.get_or_404(id)
    
    if sale_return.returned_to_inventory:
        flash('This return has already been added back to inventory.', 'warning')
        return redirect(url_for('returns.return_detail', id=id))

    # Update inventory for each item (rejected qty already logged at return creation)
    for item in sale_return.items:
        product = Product.query.get(item.product_id)
        if product:
            # update global product quantity
            product.update_quantity(item.quantity)

            # update per-warehouse stock if recorded
            try:
                wh_id = getattr(item, 'warehouse_id', None)
            except Exception:
                wh_id = None
            if wh_id:
                wh_stock = ProductWarehouseStock.query.filter_by(product_id=item.product_id, warehouse_id=wh_id).first()
                if not wh_stock:
                    wh_stock = ProductWarehouseStock(product_id=item.product_id, warehouse_id=wh_id, quantity=0)
                    db.session.add(wh_stock)
                wh_stock.quantity += item.quantity
            elif product.warehouse_id:
                wh_stock = ProductWarehouseStock.query.filter_by(product_id=item.product_id, warehouse_id=product.warehouse_id).first()
                if not wh_stock:
                    wh_stock = ProductWarehouseStock(product_id=item.product_id, warehouse_id=product.warehouse_id, quantity=0)
                    db.session.add(wh_stock)
                wh_stock.quantity += item.quantity

    sale_return.returned_to_inventory = True
    sale_return.status = 'completed'
    db.session.commit()

    flash(f'Return {sale_return.return_number} items added back to inventory.', 'success')
    return redirect(url_for('returns.return_detail', id=id))


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('returns', action='delete')
def delete_return(id):
    sale_return = SaleReturn.query.get_or_404(id)
    sale = sale_return.sale

    # Reverse inventory changes only if it was already added back
    if sale_return.returned_to_inventory:
        for item in sale_return.items:
            product = Product.query.get(item.product_id)
            if product:
                # reduce global product quantity
                product.update_quantity(-item.quantity)

                # reduce per-warehouse stock if recorded
                try:
                    wh_id = getattr(item, 'warehouse_id', None)
                except Exception:
                    wh_id = None
                if wh_id:
                    wh_stock = ProductWarehouseStock.query.filter_by(product_id=item.product_id, warehouse_id=wh_id).first()
                    if wh_stock:
                        wh_stock.quantity -= item.quantity
                elif product.warehouse_id:
                    wh_stock = ProductWarehouseStock.query.filter_by(product_id=item.product_id, warehouse_id=product.warehouse_id).first()
                    if wh_stock:
                        wh_stock.quantity -= item.quantity

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

    # --- Reverse financial changes made when the return was created ---
    
    # 1. Find and delete any auto-generated advance that was created for excess credit
    #    from this return. The description contains the return number as the identifier.
    auto_advance = CustomerAdvance.query.filter(
        CustomerAdvance.customer_id == sale.customer_id,
        CustomerAdvance.description.like(f"%Return {sale_return.return_number} excess%")
    ).first()
    
    excess_from_advance = 0.0
    if auto_advance:
        excess_from_advance = float(auto_advance.amount)
        db.session.delete(auto_advance)
    
    # 2. Capture return total BEFORE removing the return from the relationship
    return_total = float(sale_return.total or 0)
    
    # 3. Explicitly remove the return so calculate_totals doesn't count it.
    if sale_return in sale.returns:
        sale.returns.remove(sale_return)
    db.session.delete(sale_return)

    # 4. Recalculate invoice totals (this restores the original higher total)
    sale.calculate_totals()
    
    # 5. Restore paid_amount from the ACTUAL payment records (ground truth).
    #    Do NOT try to add/subtract amounts — just sum what's really been paid.
    from app.models import Payment as PaymentModel
    actual_paid = db.session.query(
        db.func.coalesce(db.func.sum(PaymentModel.amount), 0)
    ).filter(
        PaymentModel.invoice_id == sale.id,
        PaymentModel.is_approved == True
    ).scalar()
    
    # Also include any advance that was applied directly to this invoice
    advance_applied = float(sale.advance_applied or 0)
    
    # Cap at the restored invoice total
    sale.paid_amount = min(float(actual_paid) + advance_applied, sale.total)
    
    sale.update_status()
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
@permission_required('returns', action='edit')
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
