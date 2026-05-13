from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.utils import permission_required, log_activity
from app import db
from app.models import (
    ToolReceiving, ToolReceivingItem, ToolDelivering, ToolDeliveringItem, 
    ToolSettings, Product, Expense, ExpenseCategory, Company
)
from datetime import datetime

bp = Blueprint('tools', __name__)

def get_tool_settings():
    settings = ToolSettings.query.first()
    if not settings:
        settings = ToolSettings()
        db.session.add(settings)
        db.session.commit()
    return settings

@bp.route('/receiving')
@login_required
@permission_required('receiving', action='view')
def receiving_list():
    query = ToolReceiving.query
    
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    product_id = request.args.get('product_id')
    
    if from_date:
        try:
            query = query.filter(ToolReceiving.date >= datetime.strptime(from_date, '%Y-%m-%d'))
        except: pass
    if to_date:
        try:
            query = query.filter(ToolReceiving.date <= datetime.strptime(to_date, '%Y-%m-%d'))
        except: pass
    if product_id:
        query = query.join(ToolReceivingItem).filter(ToolReceivingItem.product_id == product_id)

    receivings = query.order_by(ToolReceiving.date.desc()).all()
    products = Product.query.filter_by(is_active=True).all()
    company = Company.query.first()
    date_format = company.date_format if company and company.date_format else '%Y-%m-%d'
    return render_template('tools/receiving_list.html', 
                          receivings=receivings, 
                          products=products,
                          date_format=date_format,
                          filters=request.args)

@bp.route('/receiving/create', methods=['GET', 'POST'])
@login_required
@permission_required('receiving', action='add')
def create_receiving():
    products = Product.query.filter_by(is_active=True).all()
    settings = get_tool_settings()
    
    if request.method == 'POST':
        tool_name = request.form.get('tool_name')
        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.utcnow()
        description = request.form.get('description')
        shipping_charges = float(request.form.get('shipping_charges') or 0)
        
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]') # selling price
        
        total_items_amount = 0
        valid_items = []
        
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                qty = float(quantities[i])
                price = float(prices[i])
                total = qty * price
                total_items_amount += total
                valid_items.append({
                    'product_id': int(product_ids[i]),
                    'quantity': qty,
                    'unit_price': price,
                    'total': total
                })
        
        if not valid_items:
            flash('Please add at least one item.', 'danger')
            return redirect(url_for('tools.create_receiving'))
            
        grand_total = total_items_amount + shipping_charges
        
        # Generate receiving number
        receiving_number = f"{settings.receiving_prefix}{settings.next_receiving_number}"
        settings.next_receiving_number += 1
        
        # 1. Create Expense record
        # Find or create "Tools Expense" category
        category = ExpenseCategory.query.filter_by(name='Tools Expense').first()
        if not category:
            category = ExpenseCategory(name='Tools Expense', description='Expenses related to internal tools')
            db.session.add(category)
            db.session.flush()
            
        expense = Expense(
            expense_number=f"EXP-TOOL-{receiving_number}",
            description=f"Tool Receiving #{receiving_number}: {tool_name}",
            amount=grand_total,
            date=date,
            category_id=category.id,
            status='confirmed', # Auto-confirm to reflect in P&L
            created_by=current_user.id
        )
        db.session.add(expense)
        db.session.flush()
        
        # 2. Create ToolReceiving
        receiving = ToolReceiving(
            receiving_number=receiving_number,
            tool_name=tool_name,
            date=date,
            description=description,
            shipping_charges=shipping_charges,
            total_amount=grand_total,
            expense_id=expense.id,
            created_by=current_user.id
        )
        db.session.add(receiving)
        db.session.flush()
        
        # 3. Create Items and Update Inventory
        for item in valid_items:
            rec_item = ToolReceivingItem(
                receiving_id=receiving.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                total=item['total']
            )
            db.session.add(rec_item)
            
            # Update quantity (Receiving increases stock)
            product = Product.query.get(item['product_id'])
            if product:
                product.update_quantity(item['quantity'])
        
        db.session.commit()
        
        log_activity('Tools', f'Received Tools #{receiving_number}', f'Batch: {tool_name}, Total: {grand_total}')
        flash(f'Tool Receiving #{receiving_number} created successfully!', 'success')
        return redirect(url_for('tools.receiving_list'))
        
    return render_template('tools/create_receiving.html', products=products, now=datetime.now())

@bp.route('/delivering')
@login_required
@permission_required('delivering', action='view')
def delivering_list():
    query = ToolDelivering.query
    
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    product_id = request.args.get('product_id')
    
    if from_date:
        try:
            query = query.filter(ToolDelivering.date >= datetime.strptime(from_date, '%Y-%m-%d'))
        except: pass
    if to_date:
        try:
            query = query.filter(ToolDelivering.date <= datetime.strptime(to_date, '%Y-%m-%d'))
        except: pass
    if product_id:
        query = query.join(ToolDeliveringItem).filter(ToolDeliveringItem.product_id == product_id)

    deliverings = query.order_by(ToolDelivering.date.desc()).all()
    products = Product.query.filter_by(is_active=True).all()
    company = Company.query.first()
    date_format = company.date_format if company and company.date_format else '%Y-%m-%d'
    return render_template('tools/delivering_list.html', 
                          deliverings=deliverings, 
                          products=products,
                          date_format=date_format,
                          filters=request.args)

@bp.route('/delivering/create', methods=['GET', 'POST'])
@login_required
@permission_required('delivering', action='add')
def create_delivering():
    products = Product.query.filter_by(is_active=True).all()
    settings = get_tool_settings()
    
    if request.method == 'POST':
        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.utcnow()
        description = request.form.get('description')
        
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        
        valid_items = []
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                valid_items.append({
                    'product_id': int(product_ids[i]),
                    'quantity': float(quantities[i])
                })
                
        if not valid_items:
            flash('Please add at least one item.', 'danger')
            return redirect(url_for('tools.create_delivering'))
            
        delivering_number = f"{settings.delivering_prefix}{settings.next_delivering_number}"
        settings.next_delivering_number += 1
        
        delivering = ToolDelivering(
            delivering_number=delivering_number,
            date=date,
            description=description,
            created_by=current_user.id
        )
        db.session.add(delivering)
        db.session.flush()
        
        for item in valid_items:
            del_item = ToolDeliveringItem(
                delivering_id=delivering.id,
                product_id=item['product_id'],
                quantity=item['quantity']
            )
            db.session.add(del_item)
            
            # Update quantity
            product = Product.query.get(item['product_id'])
            if product:
                product.update_quantity(-item['quantity'])
                
        db.session.commit()
        
        log_activity('Tools', f'Delivered Tools #{delivering_number}', f'Description: {description}')
        flash(f'Tool Delivering #{delivering_number} successful!', 'success')
        return redirect(url_for('tools.delivering_list'))
        
    return render_template('tools/create_delivering.html', products=products, now=datetime.now())

@bp.route('/receiving/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('receiving', action='delete')

def delete_receiving(id):
    receiving = ToolReceiving.query.get_or_404(id)
    
    # 1. Revert inventory
    for item in receiving.items:
        product = Product.query.get(item.product_id)
        if product:
            product.update_quantity(-item.quantity)
            
    # 2. Delete linked expense
    if receiving.expense_id:
        expense = Expense.query.get(receiving.expense_id)
        if expense:
            db.session.delete(expense)
            
    db.session.delete(receiving)
    db.session.commit()
    
    flash('Tool Receiving deleted and inventory reverted.', 'success')
    return redirect(url_for('tools.receiving_list'))

@bp.route('/delivering/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('delivering', action='delete')

def delete_delivering(id):
    delivering = ToolDelivering.query.get_or_404(id)
    
    # 1. Revert inventory
    for item in delivering.items:
        product = Product.query.get(item.product_id)
        if product:
            product.update_quantity(item.quantity)
            
    db.session.delete(delivering)
    db.session.commit()
    
    flash('Tool Delivering deleted and inventory reverted.', 'success')
    return redirect(url_for('tools.delivering_list'))

@bp.route('/receiving/<int:id>')
@login_required
@permission_required('receiving', action='view')
def receiving_detail(id):
    receiving = ToolReceiving.query.get_or_404(id)
    company = Company.query.first()
    date_format = company.date_format if company and company.date_format else '%Y-%m-%d'
    return render_template('tools/receiving_detail.html', receiving=receiving, date_format=date_format)

@bp.route('/receiving/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('receiving', action='edit')
def edit_receiving(id):
    receiving = ToolReceiving.query.get_or_404(id)
    products = Product.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        # Revert old inventory (Receiving was +, so revert is -)
        for item in receiving.items:
            product = Product.query.get(item.product_id)
            if product:
                product.update_quantity(-item.quantity)
        
        # Delete old items
        ToolReceivingItem.query.filter_by(receiving_id=receiving.id).delete()
        
        # Update details
        receiving.tool_name = request.form.get('tool_name')
        date_str = request.form.get('date')
        receiving.date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else receiving.date
        receiving.description = request.form.get('description')
        receiving.shipping_charges = float(request.form.get('shipping_charges') or 0)
        
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        
        total_items_amount = 0
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                qty = float(quantities[i])
                price = float(prices[i])
                total = qty * price
                total_items_amount += total
                
                item = ToolReceivingItem(
                    receiving_id=receiving.id,
                    product_id=int(product_ids[i]),
                    quantity=qty,
                    unit_price=price,
                    total=total
                )
                db.session.add(item)
                
                # Update inventory (Receiving increases stock)
                product = Product.query.get(int(product_ids[i]))
                if product:
                    product.update_quantity(qty)
        
        receiving.total_amount = total_items_amount + receiving.shipping_charges
        
        # Update linked expense
        if receiving.expense:
            receiving.expense.amount = receiving.total_amount
            receiving.expense.date = receiving.date
            receiving.expense.description = f"Tool Receiving #{receiving.receiving_number}: {receiving.tool_name}"
            
        db.session.commit()
        flash('Tool Receiving updated successfully!', 'success')
        return redirect(url_for('tools.receiving_list'))
        
    return render_template('tools/edit_receiving.html', receiving=receiving, products=products)

@bp.route('/delivering/<int:id>')
@login_required
@permission_required('delivering', action='view')
def delivering_detail(id):
    delivering = ToolDelivering.query.get_or_404(id)
    company = Company.query.first()
    date_format = company.date_format if company and company.date_format else '%Y-%m-%d'
    return render_template('tools/delivering_detail.html', delivering=delivering, date_format=date_format)

@bp.route('/delivering/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('delivering', action='edit')
def edit_delivering(id):
    delivering = ToolDelivering.query.get_or_404(id)
    products = Product.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        # Revert old inventory
        for item in delivering.items:
            product = Product.query.get(item.product_id)
            if product:
                product.update_quantity(item.quantity)
        
        # Delete old items
        ToolDeliveringItem.query.filter_by(delivering_id=delivering.id).delete()
        
        # Update details
        date_str = request.form.get('date')
        delivering.date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else delivering.date
        delivering.description = request.form.get('description')
        
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                qty = float(quantities[i])
                item = ToolDeliveringItem(
                    delivering_id=delivering.id,
                    product_id=int(product_ids[i]),
                    quantity=qty
                )
                db.session.add(item)
                
                # Update inventory
                product = Product.query.get(int(product_ids[i]))
                if product:
                    product.update_quantity(-qty)
                    
        db.session.commit()
        flash('Tool Delivering updated successfully!', 'success')
        return redirect(url_for('tools.delivering_list'))
        
    return render_template('tools/edit_delivering.html', delivering=delivering, products=products)

@bp.route('/receiving/bulk-delete', methods=['POST'])
@login_required
@permission_required('receiving', action='delete')

def bulk_delete_receiving():
    ids = request.form.getlist('ids[]')
    for id in ids:
        receiving = ToolReceiving.query.get(id)
        if receiving:
            for item in receiving.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(-item.quantity)
            if receiving.expense_id:
                expense = Expense.query.get(receiving.expense_id)
                if expense:
                    db.session.delete(expense)
            db.session.delete(receiving)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Deleted {len(ids)} receiving records.'})

@bp.route('/delivering/bulk-delete', methods=['POST'])
@login_required
@permission_required('delivering', action='delete')

def bulk_delete_delivering():
    ids = request.form.getlist('ids[]')
    for id in ids:
        delivering = ToolDelivering.query.get(id)
        if delivering:
            for item in delivering.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(item.quantity)
            db.session.delete(delivering)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Deleted {len(ids)} delivering records.'})

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@permission_required('receiving', action='view') # Fallback for settings
def settings():
    settings = get_tool_settings()
    if request.method == 'POST':
        settings.receiving_prefix = request.form.get('receiving_prefix')
        settings.delivering_prefix = request.form.get('delivering_prefix')
        settings.next_receiving_number = int(request.form.get('next_receiving_number') or 1)
        settings.next_delivering_number = int(request.form.get('next_delivering_number') or 1)
        db.session.commit()
        flash('Tool settings updated.', 'success')
        return redirect(url_for('tools.settings'))
    return render_template('tools/settings.html', settings=settings)
