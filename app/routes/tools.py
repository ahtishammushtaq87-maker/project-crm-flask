from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.utils import permission_required, log_activity
from app import db
from app.models import (
    ToolReceiving, ToolReceivingItem, ToolDelivering, ToolDeliveringItem, 
    ToolSettings, Product, Expense, ExpenseCategory, Company, Staff, Vendor,
    ManufacturingOrder, BOM
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
        
        buyer_id = request.form.get('buyer_id')
        vendor_id = request.form.get('vendor_id')
        requester_id = request.form.get('requester_id')
        
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
        
        # BOM Overhead Allocation logic
        is_bom_overhead = request.form.get('is_bom_overhead') == 'on'
        overhead_mode = request.form.get('overhead_mode', 'mo')
        
        bill_image_path = None
        if 'bill_image' in request.files:
            bill_file = request.files['bill_image']
            if bill_file and bill_file.filename:
                import os
                from werkzeug.utils import secure_filename
                filename = secure_filename(bill_file.filename)
                bill_path = os.path.join('app', 'static', 'uploads', 'bills', filename)
                os.makedirs(os.path.dirname(bill_path), exist_ok=True)
                bill_file.save(bill_path)
                bill_image_path = bill_path.replace('\\', '/')

        # 1. Create ToolReceiving
        receiving = ToolReceiving(
            receiving_number=receiving_number,
            tool_name=tool_name,
            date=date,
            description=description,
            shipping_charges=shipping_charges,
            total_amount=grand_total,
            bill_image_path=bill_image_path,
            expense_id=None,
            buyer_id=int(buyer_id) if buyer_id else None,
            vendor_id=int(vendor_id) if vendor_id else None,
            requester_id=int(requester_id) if requester_id else None,
            created_by=current_user.id,
            is_bom_overhead=is_bom_overhead,
            overhead_type=overhead_mode if is_bom_overhead else None
        )
        
        db.session.add(receiving)
        db.session.flush()

        # Handle Expense Creation for BOM Overhead
        if is_bom_overhead and grand_total > 0:
            # Prepare common expense data
            from app.routes.accounting import get_unique_expense_number
            from app.models import ExpenseSettings
            acc_settings = ExpenseSettings.query.first()
            if not acc_settings:
                acc_settings = ExpenseSettings()
                db.session.add(acc_settings)
                db.session.commit()
            
            next_num = acc_settings.next_number
            category = ExpenseCategory.query.filter_by(name='BOM Overhead').first()
            if not category:
                category = ExpenseCategory(name='BOM Overhead', description='Automatically created for BOM overhead costs')
                db.session.add(category)
                db.session.commit()

            common_kwargs = {
                'category_id': category.id,
                'vendor_id': receiving.vendor_id,
                'date': receiving.date,
                'description': f"BOM Overhead from Tool Receiving #{receiving_number}",
                'payment_method': 'Cash', # Default
                'reference': receiving_number,
                'is_bom_overhead': True
            }

            allocated_ids = []
            if overhead_mode == 'mo':
                mo_ids = request.form.getlist('mo_ids[]')
                valid_mos = ManufacturingOrder.query.filter(ManufacturingOrder.id.in_(mo_ids)).all()
                allocated_ids = [str(mo.id) for mo in valid_mos]
                
                if valid_mos:
                    amount_per_mo = grand_total / len(valid_mos)
                    for mo in valid_mos:
                        exp_num, next_num = get_unique_expense_number(acc_settings, next_num)
                        exp = Expense(
                            expense_number=exp_num,
                            amount=amount_per_mo,
                            status='confirmed',
                            mo_id=mo.id,
                            created_by=current_user.id,
                            **common_kwargs
                        )
                        db.session.add(exp)
                        # Update MO overhead
                        mo.actual_overhead_cost = (mo.actual_overhead_cost or 0) + amount_per_mo
                        mo.total_cost = (mo.actual_material_cost or 0) + (mo.actual_labor_cost or 0) + mo.actual_overhead_cost
                else:
                    # No MOs selected, create one unassigned expense
                    exp_num, next_num = get_unique_expense_number(acc_settings, next_num)
                    exp = Expense(expense_number=exp_num, amount=grand_total, status='confirmed', created_by=current_user.id, **common_kwargs)
                    db.session.add(exp)
            else:
                # Bulk Split mode
                product_ids = request.form.getlist('product_ids[]')
                bom_ids = request.form.getlist('bom_ids[]')
                
                targets = []
                for pid in product_ids:
                    if pid: targets.append(('product', int(pid)))
                for bid in bom_ids:
                    if bid: targets.append(('bom', int(bid)))
                
                allocated_ids = [f"{t}:{id}" for t, id in targets]
                
                if targets:
                    num_targets = len(targets)
                    amount_per = grand_total / num_targets
                    for target_type, target_id in targets:
                        exp_num, next_num = get_unique_expense_number(acc_settings, next_num)
                        exp_kwargs = dict(common_kwargs)
                        if target_type == 'product':
                            exp_kwargs['product_id'] = target_id
                        else:
                            exp_kwargs['bom_id'] = target_id
                            
                        exp = Expense(
                            expense_number=exp_num,
                            amount=amount_per,
                            status='confirmed',
                            created_by=current_user.id,
                            **exp_kwargs
                        )
                        db.session.add(exp)
                else:
                    # Unassigned
                    exp_num, next_num = get_unique_expense_number(acc_settings, next_num)
                    exp = Expense(expense_number=exp_num, amount=grand_total, status='confirmed', created_by=current_user.id, **common_kwargs)
                    db.session.add(exp)
            
            receiving.allocated_ids = ",".join(allocated_ids)
            acc_settings.next_number = next_num
        
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
                product.cost_price = item['unit_price']
        
        db.session.commit()
        
        log_activity('Tools', f'Received Tools #{receiving_number}', f'Batch: {tool_name}, Total: {grand_total}')
        flash(f'Tool Receiving #{receiving_number} created successfully!', 'success')
        return redirect(url_for('tools.receiving_list'))
        
    staff = Staff.query.filter_by(is_active=True).all()
    vendors = Vendor.query.filter_by(is_active=True).all()
    
    # BOM Overhead Allocation data
    in_progress_mos = ManufacturingOrder.query.filter_by(status='In Progress').order_by(ManufacturingOrder.order_number).all()
    manufactured_products = Product.query.filter_by(is_active=True).order_by(Product.name).all() # Could filter by is_manufactured
    boms = BOM.query.filter_by(is_active=True).order_by(BOM.name).all()
    
    return render_template('tools/create_receiving.html', 
                          products=products, 
                          staff=staff, 
                          vendors=vendors, 
                          now=datetime.now(),
                          in_progress_mos=in_progress_mos,
                          manufactured_products=manufactured_products,
                          boms=boms)

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
        
        buyer_id = request.form.get('buyer_id')
        vendor_id = request.form.get('vendor_id')
        requester_id = request.form.get('requester_id')
        shipping_charges = float(request.form.get('shipping_charges') or 0)
        
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        
        valid_items = []
        grand_total = 0
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                qty = float(quantities[i])
                price = float(prices[i] if i < len(prices) else 0)
                total = qty * price
                valid_items.append({
                    'product_id': int(product_ids[i]),
                    'quantity': qty,
                    'unit_price': price,
                    'total': total
                })
                grand_total += total
                
        if not valid_items:
            flash('Please add at least one item.', 'danger')
            return redirect(url_for('tools.create_delivering'))
            
        grand_total += shipping_charges
        delivering_number = f"{settings.delivering_prefix}{settings.next_delivering_number}"
        settings.next_delivering_number += 1
        
        bill_image_path = None
        if 'bill_image' in request.files:
            bill_file = request.files['bill_image']
            if bill_file and bill_file.filename:
                import os
                from werkzeug.utils import secure_filename
                filename = secure_filename(bill_file.filename)
                bill_path = os.path.join('app', 'static', 'uploads', 'bills', filename)
                os.makedirs(os.path.dirname(bill_path), exist_ok=True)
                bill_file.save(bill_path)
                bill_image_path = bill_path.replace('\\', '/')
        
        # 1. Create Expense record
        category = ExpenseCategory.query.filter_by(name='Tools Expense').first()
        if not category:
            category = ExpenseCategory(name='Tools Expense', description='Expenses related to internal tools')
            db.session.add(category)
            db.session.flush()
            
        expense = Expense(
            expense_number=f"EXP-TOOL-DEL-{delivering_number}",
            description=f"Tool Delivery #{delivering_number}: {description[:50]}",
            amount=grand_total,
            date=date,
            category_id=category.id,
            status='confirmed',
            created_by=current_user.id
        )
        db.session.add(expense)
        db.session.flush()
        
        # 2. Create ToolDelivering
        delivering = ToolDelivering(
            delivering_number=delivering_number,
            date=date,
            description=description,
            shipping_charges=shipping_charges,
            total_amount=grand_total,
            bill_image_path=bill_image_path,
            expense_id=expense.id,
            buyer_id=int(buyer_id) if buyer_id else None,
            vendor_id=int(vendor_id) if vendor_id else None,
            requester_id=int(requester_id) if requester_id else None,
            created_by=current_user.id
        )
        db.session.add(delivering)
        db.session.flush()
        
        for item in valid_items:
            del_item = ToolDeliveringItem(
                delivering_id=delivering.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                total=item['total']
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
        
    staff = Staff.query.filter_by(is_active=True).all()
    vendors = Vendor.query.filter_by(is_active=True).all()
    return render_template('tools/create_delivering.html', products=products, staff=staff, vendors=vendors, now=datetime.now())

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
            
    # 2. Delete linked overhead expenses and update MO costs
    expenses = Expense.query.filter_by(reference=receiving.receiving_number).all()
    for exp in expenses:
        if exp.is_bom_overhead and exp.mo_id:
            mo = ManufacturingOrder.query.get(exp.mo_id)
            if mo and exp.status == 'confirmed':
                mo.actual_overhead_cost = max(0, (mo.actual_overhead_cost or 0) - exp.amount)
                mo.total_cost = (mo.actual_material_cost or 0) + (mo.actual_labor_cost or 0) + mo.actual_overhead_cost
        db.session.delete(exp)
            
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
            
    # 2. Delete linked expense
    if delivering.expense:
        db.session.delete(delivering.expense)
            
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
        
        receiving.buyer_id = int(request.form.get('buyer_id')) if request.form.get('buyer_id') else None
        receiving.vendor_id = int(request.form.get('vendor_id')) if request.form.get('vendor_id') else None
        receiving.requester_id = int(request.form.get('requester_id')) if request.form.get('requester_id') else None
        
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
                    product.cost_price = price
        
        receiving.total_amount = total_items_amount + receiving.shipping_charges
        
        if 'bill_image' in request.files:
            bill_file = request.files['bill_image']
            if bill_file and bill_file.filename:
                import os
                from werkzeug.utils import secure_filename
                filename = secure_filename(bill_file.filename)
                bill_path = os.path.join('app', 'static', 'uploads', 'bills', filename)
                os.makedirs(os.path.dirname(bill_path), exist_ok=True)
                bill_file.save(bill_path)
                receiving.bill_image_path = bill_path.replace('\\', '/')
        
        # BOM Overhead Allocation logic
        is_bom_overhead = request.form.get('is_bom_overhead') == 'on'
        overhead_mode = request.form.get('overhead_mode', 'mo')
        
        # Update Receiving overhead fields
        receiving.is_bom_overhead = is_bom_overhead
        receiving.overhead_type = overhead_mode if is_bom_overhead else None
        
        # Cleanup old expenses and revert MO costs
        old_expenses = Expense.query.filter_by(reference=receiving.receiving_number).all()
        for exp in old_expenses:
            if exp.is_bom_overhead and exp.mo_id:
                mo = ManufacturingOrder.query.get(exp.mo_id)
                if mo and exp.status == 'confirmed':
                    mo.actual_overhead_cost = max(0, (mo.actual_overhead_cost or 0) - exp.amount)
                    mo.total_cost = (mo.actual_material_cost or 0) + (mo.actual_labor_cost or 0) + mo.actual_overhead_cost
            db.session.delete(exp)
        
        # Re-create Expenses if needed
        if is_bom_overhead and receiving.total_amount > 0:
            from app.routes.accounting import get_unique_expense_number
            from app.models import ExpenseSettings
            acc_settings = ExpenseSettings.query.first() or ExpenseSettings()
            if not acc_settings.id: db.session.add(acc_settings); db.session.flush()
            
            next_num = acc_settings.next_number
            category = ExpenseCategory.query.filter_by(name='BOM Overhead').first()
            if not category:
                category = ExpenseCategory(name='BOM Overhead', description='Automatically created for BOM overhead costs')
                db.session.add(category)
                db.session.flush()

            common_kwargs = {
                'category_id': category.id,
                'vendor_id': receiving.vendor_id,
                'date': receiving.date,
                'description': f"BOM Overhead from Tool Receiving #{receiving.receiving_number} (Updated)",
                'payment_method': 'Cash',
                'reference': receiving.receiving_number,
                'is_bom_overhead': True
            }

            allocated_ids = []
            if overhead_mode == 'mo':
                mo_ids = request.form.getlist('mo_ids[]')
                valid_mos = ManufacturingOrder.query.filter(ManufacturingOrder.id.in_(mo_ids)).all()
                allocated_ids = [str(mo.id) for mo in valid_mos]
                
                if valid_mos:
                    amount_per_mo = receiving.total_amount / len(valid_mos)
                    for mo in valid_mos:
                        exp_num, next_num = get_unique_expense_number(acc_settings, next_num)
                        exp = Expense(
                            expense_number=exp_num,
                            amount=amount_per_mo,
                            status='confirmed',
                            mo_id=mo.id,
                            created_by=current_user.id,
                            **common_kwargs
                        )
                        db.session.add(exp)
                        mo.actual_overhead_cost = (mo.actual_overhead_cost or 0) + amount_per_mo
                        mo.total_cost = (mo.actual_material_cost or 0) + (mo.actual_labor_cost or 0) + mo.actual_overhead_cost
                else:
                    exp_num, next_num = get_unique_expense_number(acc_settings, next_num)
                    exp = Expense(expense_number=exp_num, amount=receiving.total_amount, status='confirmed', created_by=current_user.id, **common_kwargs)
                    db.session.add(exp)
            else:
                # Bulk Split mode
                product_ids = request.form.getlist('product_ids[]')
                bom_ids = request.form.getlist('bom_ids[]')
                targets = []
                for pid in product_ids:
                    if pid: targets.append(('product', int(pid)))
                for bid in bom_ids:
                    if bid: targets.append(('bom', int(bid)))
                
                allocated_ids = [f"{t}:{id}" for t, id in targets]
                
                if targets:
                    num_targets = len(targets)
                    amount_per = receiving.total_amount / num_targets
                    for target_type, target_id in targets:
                        exp_num, next_num = get_unique_expense_number(acc_settings, next_num)
                        exp_kwargs = dict(common_kwargs)
                        if target_type == 'product': exp_kwargs['product_id'] = target_id
                        else: exp_kwargs['bom_id'] = target_id
                        exp = Expense(expense_number=exp_num, amount=amount_per, status='confirmed', created_by=current_user.id, **exp_kwargs)
                        db.session.add(exp)
                else:
                    exp_num, next_num = get_unique_expense_number(acc_settings, next_num)
                    exp = Expense(expense_number=exp_num, amount=receiving.total_amount, status='confirmed', created_by=current_user.id, **common_kwargs)
                    db.session.add(exp)
            
            receiving.allocated_ids = ",".join(allocated_ids)
            acc_settings.next_number = next_num

        db.session.commit()
        flash('Tool Receiving updated successfully!', 'success')
        return redirect(url_for('tools.receiving_list'))
        
    staff = Staff.query.filter_by(is_active=True).all()
    vendors = Vendor.query.filter_by(is_active=True).all()
    
    # BOM Overhead Allocation data
    in_progress_mos = ManufacturingOrder.query.filter_by(status='In Progress').order_by(ManufacturingOrder.order_number).all()
    manufactured_products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    boms = BOM.query.filter_by(is_active=True).order_by(BOM.name).all()
    
    # Pre-process allocated_ids for the template (already stored as comma separated string)
    allocated_list = receiving.allocated_ids.split(',') if receiving.allocated_ids else []
    
    return render_template('tools/edit_receiving.html', 
                          receiving=receiving, 
                          products=products, 
                          staff=staff, 
                          vendors=vendors,
                          in_progress_mos=in_progress_mos,
                          manufactured_products=manufactured_products,
                          boms=boms,
                          allocated_list=allocated_list)

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
        delivering.shipping_charges = float(request.form.get('shipping_charges') or 0)
        
        delivering.buyer_id = int(request.form.get('buyer_id')) if request.form.get('buyer_id') else None
        delivering.vendor_id = int(request.form.get('vendor_id')) if request.form.get('vendor_id') else None
        delivering.requester_id = int(request.form.get('requester_id')) if request.form.get('requester_id') else None
        
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        
        total_items_amount = 0
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                qty = float(quantities[i])
                price = float(prices[i] if i < len(prices) else 0)
                total = qty * price
                total_items_amount += total
                
                item = ToolDeliveringItem(
                    delivering_id=delivering.id,
                    product_id=int(product_ids[i]),
                    quantity=qty,
                    unit_price=price,
                    total=total
                )
                db.session.add(item)
                
                # Update inventory
                product = Product.query.get(int(product_ids[i]))
                if product:
                    product.update_quantity(-qty)
        
        delivering.total_amount = total_items_amount + delivering.shipping_charges
        
        if 'bill_image' in request.files:
            bill_file = request.files['bill_image']
            if bill_file and bill_file.filename:
                import os
                from werkzeug.utils import secure_filename
                filename = secure_filename(bill_file.filename)
                bill_path = os.path.join('app', 'static', 'uploads', 'bills', filename)
                os.makedirs(os.path.dirname(bill_path), exist_ok=True)
                bill_file.save(bill_path)
                delivering.bill_image_path = bill_path.replace('\\', '/')
        
        # Update or create linked expense
        if not delivering.expense:
            category = ExpenseCategory.query.filter_by(name='Tools Expense').first()
            if not category:
                category = ExpenseCategory(name='Tools Expense', description='Expenses related to internal tools')
                db.session.add(category)
                db.session.flush()
                
            expense = Expense(
                expense_number=f"EXP-TOOL-DEL-{delivering.delivering_number}",
                description=f"Tool Delivery #{delivering.delivering_number}: {delivering.description[:50]}",
                amount=delivering.total_amount,
                date=delivering.date,
                category_id=category.id,
                status='confirmed',
                created_by=current_user.id
            )
            db.session.add(expense)
            db.session.flush()
            delivering.expense_id = expense.id
        else:
            delivering.expense.amount = delivering.total_amount
            delivering.expense.date = delivering.date
            delivering.expense.description = f"Tool Delivery #{delivering.delivering_number}: {delivering.description[:50]}"
            
        db.session.commit()
        flash('Tool Delivering updated successfully!', 'success')
        return redirect(url_for('tools.delivering_list'))
        
    staff = Staff.query.filter_by(is_active=True).all()
    vendors = Vendor.query.filter_by(is_active=True).all()
    return render_template('tools/edit_delivering.html', delivering=delivering, products=products, staff=staff, vendors=vendors)

@bp.route('/receiving/bulk-delete', methods=['POST'])
@login_required
@permission_required('receiving', action='delete')

def bulk_delete_receiving():
    if request.is_json:
        ids = request.json.get('ids', [])
    else:
        ids = request.form.getlist('ids[]')
    
    for id in ids:
        receiving = ToolReceiving.query.get(id)
        if receiving:
            for item in receiving.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(-item.quantity)
            expenses = Expense.query.filter_by(reference=receiving.receiving_number).all()
            for exp in expenses:
                if exp.is_bom_overhead and exp.mo_id:
                    mo = ManufacturingOrder.query.get(exp.mo_id)
                    if mo and exp.status == 'confirmed':
                        mo.actual_overhead_cost = max(0, (mo.actual_overhead_cost or 0) - exp.amount)
                        mo.total_cost = (mo.actual_material_cost or 0) + (mo.actual_labor_cost or 0) + mo.actual_overhead_cost
                db.session.delete(exp)
            db.session.delete(receiving)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Deleted {len(ids)} receiving records.'})

@bp.route('/delivering/bulk-delete', methods=['POST'])
@login_required
@permission_required('delivering', action='delete')

def bulk_delete_delivering():
    if request.is_json:
        ids = request.json.get('ids', [])
    else:
        ids = request.form.getlist('ids[]')
        
    for id in ids:
        delivering = ToolDelivering.query.get(id)
        if delivering:
            for item in delivering.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(item.quantity)
            if delivering.expense:
                db.session.delete(delivering.expense)
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
