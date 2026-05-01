from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Product, BOM, BOMItem, ManufacturingOrder, ManufacturingOrderItem, StockMovement, BOMVersion, Company, Expense
from app.forms import BOMForm, ManufacturingOrderForm
from app.services.bom_versioning import BOMVersioningService
from datetime import datetime
from sqlalchemy import inspect, or_

bp = Blueprint('manufacturing', __name__)

def has_column(table_name, column_name):
    try:
        inspector = inspect(db.engine)
        return column_name in [c['name'] for c in inspector.get_columns(table_name)]
    except:
        return False

@bp.route('/boms')
@login_required
def boms():
    boms = BOM.query.all()
    return render_template('manufacturing/boms.html', boms=boms)

@bp.route('/bom/add', methods=['GET', 'POST'])
@login_required
def add_bom():
    form = BOMForm()
    # Only show manufactured products in the "Finished Product" dropdown (if column exists)
    if has_column('products', 'is_manufactured'):
        manufactured_products = Product.query.filter_by(is_manufactured=True).all()
    else:
        manufactured_products = []
    form.product_id.choices = [(p.id, f"{p.sku} - {p.name}") for p in manufactured_products]
    
    # All products can be components (except maybe the finished product itself)
    all_products = Product.query.all()

    if form.validate_on_submit():
        bom = BOM(
            name=form.name.data,
            product_id=form.product_id.data,
            labor_cost=form.labor_cost.data or 0,
            overhead_cost=form.overhead_cost.data or 0,
            version='v1',
            is_active=True
        )
        db.session.add(bom)
        db.session.flush() # Get bom.id
        
        # Process components (submitted via dynamic form elements)
        component_ids = request.form.getlist('component_id[]')
        quantities = request.form.getlist('quantity[]')
        
        for comp_id, qty in zip(component_ids, quantities):
            if comp_id and qty:
                comp_product = Product.query.get(comp_id)
                if comp_product:
                    # Calculate item cost with shipping (if available)
                    unit_cost = comp_product.cost_price
                    qty_float = float(qty)
                    total_cost = unit_cost * qty_float
                    
                    item = BOMItem(
                        bom_id=bom.id,
                        component_id=comp_id,
                        quantity=qty_float,
                        unit_cost=unit_cost,
                        shipping_per_unit=0,  # Will be updated when purchase happens
                        total_cost=total_cost
                    )
                    db.session.add(item)
                    
        # Update total cost of BOM after items are added
        db.session.commit()
        bom.calculate_total_cost()
        
        # Link all available overhead expenses for this product to this BOM
        # and calculate total overhead cost from linked expenses
        from app.models import Expense
        if has_column('expenses', 'is_bom_overhead'):
            # Link overhead expenses to this BOM
            db.session.query(Expense).filter(
                Expense.product_id == bom.product_id,
                Expense.is_bom_overhead == True,
                Expense.bom_id == None
            ).update({Expense.bom_id: bom.id}, synchronize_session=False)
            
            # Calculate total overhead from linked expenses for this BOM
            total_linked_overhead = db.session.query(db.func.sum(Expense.amount)).filter(
                Expense.bom_id == bom.id,
                Expense.is_bom_overhead == True,
                Expense.status == 'confirmed'
            ).scalar() or 0
            
            # If there are linked overhead expenses, use that total as BOM overhead cost
            # Otherwise use the manually entered overhead cost from form
            if total_linked_overhead > 0:
                bom.overhead_cost = total_linked_overhead
                bom.calculate_total_cost()
                # Overhead cost is updated from expenses, but we don't update product.cost_price here
                # Inventory cost only changes after manufacture is complete
                # bom.product.cost_price = bom.total_cost

        # Create initial version record (v1)
        # Safe user_id resolution
        user_id = None
        try:
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
        except (AttributeError, TypeError):
            pass
        if user_id is None:
            from app.models import User as UserModel
            admin_user = UserModel.query.filter_by(username='admin').first()
            user_id = admin_user.id if admin_user else 1
        
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="Initial BOM creation",
            change_type="manual",
            created_by_id=user_id,
            recalculate_overhead=False
        )

        # We capture the BOM structure/cost in the version record, but don't the product.cost_price yet
        # Product cost will be updated upon production completion
        db.session.commit()
        
        flash('Bill of Materials created successfully (v1).', 'success')
        return redirect(url_for('manufacturing.boms'))
        
    return render_template('manufacturing/add_bom.html', form=form, all_products=all_products)

@bp.route('/bom/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bom(id):
    bom = BOM.query.get_or_404(id)
    form = BOMForm(obj=bom)
    
    # Only show manufactured products in the "Finished Product" dropdown (if column exists)
    if has_column('products', 'is_manufactured'):
        manufactured_products = Product.query.filter_by(is_manufactured=True).all()
    else:
        manufactured_products = []
        
    form.product_id.choices = [(p.id, f"{p.sku} - {p.name}") for p in manufactured_products]
    
    # Ensure current product is in choices even if not strictly 'manufactured' historically
    if bom.product_id and bom.product_id not in [p.id for p in manufactured_products]:
        p = Product.query.get(bom.product_id)
        if p:
            form.product_id.choices.append((p.id, f"{p.sku} - {p.name} (Current)"))
            
    all_products = Product.query.all()

    if form.validate_on_submit():
        bom.name = form.name.data
        bom.product_id = form.product_id.data
        bom.labor_cost = form.labor_cost.data or 0
        bom.overhead_cost = form.overhead_cost.data or 0

        # Remove existing BOMItems safely
        for item in bom.items:
            db.session.delete(item)
            
        db.session.flush() # Secure empty state

        # Process new components
        component_ids = request.form.getlist('component_id[]')
        quantities = request.form.getlist('quantity[]')
        
        for comp_id, qty in zip(component_ids, quantities):
            if comp_id and qty:
                comp_product = Product.query.get(comp_id)
                if comp_product:
                    unit_cost = comp_product.cost_price
                    qty_float = float(qty)
                    total_cost = unit_cost * qty_float
                    
                    new_item = BOMItem(
                        bom_id=bom.id,
                        component_id=comp_id,
                        quantity=qty_float,
                        unit_cost=unit_cost,
                        shipping_per_unit=0,
                        total_cost=total_cost
                    )
                    db.session.add(new_item)
                    
        db.session.commit()
        bom.calculate_total_cost()

        # Re-trigger Overhead auto-sync if expense module supports it
        from app.models import Expense
        if has_column('expenses', 'is_bom_overhead'):
            # Link overhead expenses to this BOM
            db.session.query(Expense).filter(
                Expense.product_id == bom.product_id,
                Expense.is_bom_overhead == True,
                Expense.bom_id == None
            ).update({Expense.bom_id: bom.id}, synchronize_session=False)
            
            # Calculate total overhead from linked expenses for this BOM
            total_linked_overhead = db.session.query(db.func.sum(Expense.amount)).filter(
                Expense.bom_id == bom.id,
                Expense.is_bom_overhead == True,
                Expense.status == 'confirmed'
            ).scalar() or 0
            
            if total_linked_overhead > 0:
                bom.overhead_cost = total_linked_overhead
                bom.calculate_total_cost()
                
        # Bump version safely
        user_id = None
        try:
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
        except (AttributeError, TypeError):
            pass
        if user_id is None:
            from app.models import User as UserModel
            admin_user = UserModel.query.filter_by(username='admin').first()
            user_id = admin_user.id if admin_user else 1

        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="BOM structure modified via edit",
            change_type="manual",
            created_by_id=user_id,
            recalculate_overhead=False
        )

        # Structure updated, versioned, but product.cost_price remains untouched until production
        db.session.commit()
        
        flash('Bill of Materials updated successfully.', 'success')
        return redirect(url_for('manufacturing.bom_details', id=bom.id))
        
    return render_template('manufacturing/edit_bom.html', form=form, all_products=all_products, bom=bom)

@bp.route('/bom/<int:id>')
@login_required
def bom_details(id):
    bom = BOM.query.get_or_404(id)
    return render_template('manufacturing/bom_details.html', bom=bom)

@bp.route('/bom/<int:id>/delete', methods=['GET', 'POST'])
@login_required
def delete_bom(id):
    bom = BOM.query.get_or_404(id)
    if bom.manufacturing_orders:
        flash('Cannot delete BOM because it has associated Manufacturing Orders.', 'danger')
        return redirect(url_for('manufacturing.boms'))
    
    try:
        # Manually delete all child records before deleting BOM
        # This ensures cascade delete works properly
        
        # 1. Unlink any associated overhead expenses
        from app.models import Expense, BOMVersion, BOMItem
        db.session.query(Expense).filter(Expense.bom_id == id).update(
            {Expense.bom_id: None}, 
            synchronize_session=False
        )
        
        # 2. Delete all BOM versions (which will cascade delete version items)
        bom_versions = BOMVersion.query.filter_by(bom_id=id).all()
        for version in bom_versions:
            # Delete version items first (to be explicit)
            from app.models import BOMVersionItem
            BOMVersionItem.query.filter_by(version_id=version.id).delete(synchronize_session=False)
            db.session.delete(version)
        
        # 3. Delete all BOM items
        BOMItem.query.filter_by(bom_id=id).delete(synchronize_session=False)
        
        # 4. Now delete the BOM itself
        db.session.delete(bom)
        db.session.commit()
        
        flash('BOM deleted successfully.', 'success')
        return redirect(url_for('manufacturing.boms'))
    
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting BOM: {e}")
        flash(f'Error deleting BOM: {str(e)}', 'danger')
        return redirect(url_for('manufacturing.boms'))

@bp.route('/orders')
@login_required
def orders():
    orders = ManufacturingOrder.query.order_by(ManufacturingOrder.created_at.desc()).all()
    return render_template('manufacturing/orders.html', orders=orders)

@bp.route('/order/add', methods=['GET', 'POST'])
@login_required
def add_order():
    form = ManufacturingOrderForm()
    boms = BOM.query.all()
    form.bom_id.choices = [(b.id, f"{b.name} ({b.product.sku} - {b.product.name})") for b in boms]
    
    if form.validate_on_submit():
        # Generate Unique Order Number using company settings
        company = Company.query.first()
        prefix = company.mo_prefix if company and company.mo_prefix else 'MO-'
        suffix = company.mo_suffix if company and company.mo_suffix else ''
        next_num = company.next_mo_number if company and company.next_mo_number else 1

        order_number = f"{prefix}{next_num:03d}{suffix}"

        # Increment and save next number
        company.next_mo_number = next_num + 1
        db.session.commit()  # commit early to persist next number

        # Safety check for duplicates (should not happen but guard)
        while ManufacturingOrder.query.filter_by(order_number=order_number).first():
            next_num += 1
            order_number = f"{prefix}{next_num:03d}{suffix}"
            company.next_mo_number = next_num + 1
        
        bom = BOM.query.get(form.bom_id.data)
        
        mo = ManufacturingOrder(
            order_number=order_number,
            bom_id=bom.id,
            quantity_to_produce=form.quantity_to_produce.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status='In Progress',
            created_by=current_user.id
        )
        db.session.add(mo)
        db.session.flush()
        
        # Add required items based on BOM
        multiplier = mo.quantity_to_produce
        for bom_item in bom.items:
            req_qty = bom_item.quantity * multiplier
            comp_cost = bom_item.component.cost_price * req_qty
            
            mo_item = ManufacturingOrderItem(
                mo_id=mo.id,
                component_id=bom_item.component_id,
                quantity_required=req_qty,
                quantity_consumed=0, # Consumed when completed
                cost=comp_cost
            )
            db.session.add(mo_item)

        # Collect and link unassigned overhead expenses for this order
        from app.models import Expense
        from sqlalchemy import or_
        
        unassigned_expenses = Expense.query.filter(
            Expense.is_bom_overhead == True,
            Expense.mo_id == None,
            or_(Expense.bom_id == bom.id, Expense.product_id == bom.product_id)
        ).all()
        
        total_mo_overhead = 0
        for exp in unassigned_expenses:
            exp.mo_id = mo.id
            total_mo_overhead += exp.amount
            
        mo.actual_overhead_cost = total_mo_overhead
        mo.actual_labor_cost = bom.labor_cost * multiplier
        mo.actual_material_cost = sum(item.component.cost_price * (item.quantity * multiplier) for item in bom.items)
        mo.total_cost = mo.actual_labor_cost + mo.actual_material_cost + mo.actual_overhead_cost
        
        db.session.commit()
        
        flash('Manufacturing Order created successfully.', 'success')
        return redirect(url_for('manufacturing.orders'))
        
    return render_template('manufacturing/add_order.html', form=form)

@bp.route('/order/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_order(id):
    order = ManufacturingOrder.query.get_or_404(id)
    form = ManufacturingOrderForm(obj=order)
    
    boms = BOM.query.all()
    form.bom_id.choices = [(b.id, f"{b.name} ({b.product.sku} - {b.product.name})") for b in boms]
    
    if form.validate_on_submit():
        old_bom_id = order.bom_id
        old_quantity = order.quantity_to_produce
        
        order.bom_id = form.bom_id.data
        order.quantity_to_produce = form.quantity_to_produce.data
        order.start_date = form.start_date.data
        order.end_date = form.end_date.data
        
        if old_bom_id != order.bom_id or old_quantity != order.quantity_to_produce:
            multiplier = order.quantity_to_produce
            
            for item in order.items:
                db.session.delete(item)
            db.session.flush()
            
            new_bom = BOM.query.get(order.bom_id)
            for bom_item in new_bom.items:
                req_qty = bom_item.quantity * multiplier
                comp_cost = bom_item.component.cost_price * req_qty
                
                mo_item = ManufacturingOrderItem(
                    mo_id=order.id,
                    component_id=bom_item.component_id,
                    quantity_required=req_qty,
                    quantity_consumed=0,
                    cost=comp_cost
                )
                db.session.add(mo_item)
            
            order.actual_labor_cost = new_bom.labor_cost * multiplier
            order.actual_material_cost = sum(item.component.cost_price * (item.quantity * multiplier) for item in new_bom.items)
            order.total_cost = order.actual_labor_cost + order.actual_material_cost + (order.actual_overhead_cost or 0)
        
        db.session.commit()
        flash('Manufacturing Order updated successfully.', 'success')
        return redirect(url_for('manufacturing.order_details', id=order.id))
    
    return render_template('manufacturing/edit_order.html', form=form, order=order)

@bp.route('/order/<int:id>')
@login_required
def order_details(id):
    order = ManufacturingOrder.query.get_or_404(id)
    return render_template('manufacturing/order_details.html', order=order)

@bp.route('/order/<int:id>/complete', methods=['POST'])
@login_required
def complete_order(id):
    order = ManufacturingOrder.query.get_or_404(id)
    
    if order.status == 'Completed':
        flash('Order is already completed.', 'warning')
        return redirect(url_for('manufacturing.order_details', id=order.id))
        
    # Check component inventory
    for item in order.items:
        if item.component.quantity < item.quantity_required:
            flash(f'Insufficient stock for component {item.component.name}. Required: {item.quantity_required}, Available: {item.component.quantity}', 'danger')
            return redirect(url_for('manufacturing.order_details', id=order.id))
            
    # Consume components and record stock movements
    total_material_cost = 0
    for item in order.items:
        item.quantity_consumed = item.quantity_required
        item.component.quantity -= item.quantity_consumed
        
        movement_out = StockMovement(
            product_id=item.component_id,
            movement_type='out',
            reference_type='manufacturing_usage',
            reference_id=order.id,
            quantity=item.quantity_consumed,
            previous_quantity=item.component.quantity + item.quantity_consumed,
            new_quantity=item.component.quantity,
            reason=f'Consumed in MO {order.order_number}',
            created_by=current_user.id
        )
        db.session.add(movement_out)
        total_material_cost += item.component.cost_price * item.quantity_consumed

    # Add finished good and record stock movement
    finished_good = order.bom.product
    completed_qty = order.quantity_to_produce
    finished_good.quantity += completed_qty
    
    movement_in = StockMovement(
        product_id=finished_good.id,
        movement_type='in',
        reference_type='manufacturing_finish',
        reference_id=order.id,
        quantity=completed_qty,
        previous_quantity=finished_good.quantity - completed_qty,
        new_quantity=finished_good.quantity,
        reason=f'Produced from MO {order.order_number}',
        created_by=current_user.id
    )
    db.session.add(movement_in)
    
    # Calculate costs
    order.actual_material_cost = total_material_cost
    # Keep labor cost as set during creation (based on BOM)
    order.total_cost = order.actual_material_cost + order.actual_labor_cost + order.actual_overhead_cost
    
    # Update product cost price based on actual production cost per unit
    if completed_qty > 0:
        finished_good.cost_price = order.total_cost / completed_qty
    
    # Update standard cost of finished good (Weighted Average or straight replacement based on latest production)
    # Simple replacement for this implementation
    if completed_qty > 0:
        unit_cost = order.total_cost / completed_qty
        finished_good.cost_price = unit_cost
        
    order.status = 'Completed'
    order.end_date = datetime.now().date()
    
    # Auto-create production log entry
    from app.models import ProductionLog
    production_log = ProductionLog(
        date=order.end_date,
        sku_id=finished_good.id,
        shift='Production Order',
        operator=f'MO: {order.order_number}',
        qty_produced=completed_qty,
        rejected_qty=0,
        notes=f'Auto-created from Manufacturing Order {order.order_number}',
        created_by=current_user.id
    )
    db.session.add(production_log)
    
    # Update Production Target Produced Qty if exists (Stateful Running Total)
    from app.models import ProductionTarget
    # Find target covering the production date
    target = ProductionTarget.query.filter(
        ProductionTarget.sku_id == finished_good.id,
        ProductionTarget.start_date <= order.end_date,
        ProductionTarget.end_date >= order.end_date
    ).first()
    
    if target:
        if target.produced_qty is None:
            # First time sync: initialize with current logs sum
            from sqlalchemy import func
            log_sum = db.session.query(func.sum(ProductionLog.qty_produced)).filter(
                ProductionLog.sku_id == target.sku_id,
                ProductionLog.date >= target.start_date,
                ProductionLog.date <= target.end_date
            ).scalar() or 0
            target.produced_qty = log_sum
        else:
            target.produced_qty += completed_qty
    
    db.session.commit()
    flash('Manufacturing Order completed successfully. Stock adjusted and product cost updated.', 'success')
    return redirect(url_for('manufacturing.order_details', id=order.id))

@bp.route('/api/bom/<int:id>/details')
@login_required
def get_bom_details(id):
    bom = BOM.query.get_or_404(id)
    return jsonify({
        'labor_cost': bom.labor_cost,
        'overhead_cost': bom.overhead_cost,
        'total_cost': bom.total_cost
    })

@bp.route('/api/product/<int:id>/actual-overhead')
@login_required
def get_actual_overhead(id):
    from app.models import Expense
    total_overhead = 0
    if has_column('expenses', 'is_bom_overhead'):
        total_overhead = db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.product_id == id,
            Expense.is_bom_overhead == True,
            Expense.status == 'confirmed',
            Expense.bom_id == None
        ).scalar() or 0
    return jsonify({
        'total_actual_overhead': total_overhead
    })
@bp.route('/order/<int:id>/delete', methods=['GET', 'POST'])
@login_required
def delete_order(id):
    from app.models import ManufacturingOrder, StockMovement, Product
    order = ManufacturingOrder.query.get_or_404(id)
    
    # If order is completed, we MUST reverse the stock and cost changes
    if order.status == 'Completed':
        # 1. Substract the produced quantity from the finished product
        finished_product = order.bom.product
        finished_product.quantity -= order.quantity_to_produce
        
        # 2. Add back the consumed quantities to all components
        for item in order.items:
            if item.component:
                item.component.quantity += item.quantity_consumed
        
        # 3. Revert the finished_product.cost_price
        # Find the most recent 'Completed' order for the SAME product (excluding this one)
        previous_completed_order = ManufacturingOrder.query.filter(
            ManufacturingOrder.bom.has(product_id=finished_product.id),
            ManufacturingOrder.status == 'Completed',
            ManufacturingOrder.id != order.id
        ).order_by(ManufacturingOrder.end_date.desc()).first()

        if previous_completed_order and previous_completed_order.quantity_to_produce > 0:
            finished_product.cost_price = previous_completed_order.total_cost / previous_completed_order.quantity_to_produce
        else:
            # Fallback to the current BOM's estimated cost
            order.bom.calculate_total_cost()
            finished_product.cost_price = order.bom.total_cost

        # 4. Remove associated StockMovements
        StockMovement.query.filter(
            StockMovement.reference_id == order.id,
            StockMovement.reference_type.in_(['manufacturing_consumption', 'manufacturing_finish'])
        ).delete(synchronize_session=False)

        # 5. Remove associated ProductionLog and decrease target counts
        from app.models import ProductionLog, ProductionTarget
        logs_to_delete = ProductionLog.query.filter(
            ProductionLog.operator == f'MO: {order.order_number}'
        ).all()
        
        for l in logs_to_delete:
            # Subtract from target if target is stateful
            target = ProductionTarget.query.filter(
                ProductionTarget.sku_id == order.bom.product_id,
                ProductionTarget.start_date <= l.date,
                ProductionTarget.end_date >= l.date
            ).first()
            if target and target.produced_qty is not None:
                target.produced_qty -= l.qty_produced
            db.session.delete(l)
    
    # Delete any associated overhead expenses linked to this MO
    from app.models import Expense
    linked_expenses = Expense.query.filter_by(mo_id=order.id).all()
    for exp in linked_expenses:
        db.session.delete(exp)
    
    db.session.delete(order)
    db.session.commit()
    
    flash('Manufacturing Order deleted successfully. Linked overhead expenses have been released.', 'success')
    return redirect(url_for('manufacturing.orders'))


# ─────────────────────────────────────────────────────────────────────────
# BOM VERSIONING ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────

@bp.route('/api/bom/<int:bom_id>/versions')
@login_required
def get_bom_versions(bom_id):
    """Get version history for a BOM"""
    bom = BOM.query.get_or_404(bom_id)
    versions = BOMVersioningService.get_bom_version_history(bom_id)
    
    return jsonify({
        'bom_id': bom_id,
        'bom_name': bom.name,
        'current_version': bom.version,
        'current_cost': bom.total_cost,
        'versions': [
            {
                'id': v.id,
                'version_number': v.version_number,
                'labor_cost': v.labor_cost,
                'overhead_cost': v.overhead_cost,
                'total_cost': v.total_cost,
                'change_reason': v.change_reason,
                'change_type': v.change_type,
                'previous_version': v.previous_version,
                'created_at': v.created_at.strftime('%d-%m-%Y %H:%M'),
                'created_by': v.creator.username if hasattr(v, 'creator') and v.creator else 'System'
            }
            for v in versions
        ]
    })


@bp.route('/api/bom/versions/<int:v1_id>/compare/<int:v2_id>')
@login_required
def compare_bom_versions(v1_id, v2_id):
    """Compare two BOM versions"""
    comparison = BOMVersioningService.compare_bom_versions(v1_id, v2_id)
    
    if not comparison:
        return jsonify({'error': 'Versions not found'}), 404
    
    return jsonify(comparison)


@bp.route('/api/bom/<int:bom_id>/check-updates', methods=['POST'])
@login_required
def check_bom_updates(bom_id):
    """Check if BOM needs version update due to component cost changes"""
    bom = BOM.query.get_or_404(bom_id)
    
    # Check each component for cost changes
    needs_update = False
    changed_components = []
    
    for item in bom.items:
        component = item.component
        if component and component.cost_price != item.unit_cost:
            needs_update = True
            changed_components.append({
                'name': component.name,
                'old_cost': item.unit_cost,
                'new_cost': component.cost_price,
                'difference': component.cost_price - item.unit_cost
            })
    
    return jsonify({
        'bom_id': bom_id,
        'current_version': bom.version,
        'needs_update': needs_update,
        'changed_components': changed_components
    })


@bp.route('/bom/<int:bom_id>/versions', methods=['GET'])
@login_required
def view_bom_versions(bom_id):
    """Display BOM version history page"""
    bom = BOM.query.get_or_404(bom_id)
    versions = BOMVersioningService.get_bom_version_history(bom_id)
    
    return render_template('manufacturing/bom_versions.html', bom=bom, versions=versions)
