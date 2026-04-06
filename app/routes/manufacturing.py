from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Product, BOM, BOMItem, ManufacturingOrder, ManufacturingOrderItem, StockMovement
from app.forms import BOMForm, ManufacturingOrderForm
from datetime import datetime

bp = Blueprint('manufacturing', __name__)

@bp.route('/boms')
@login_required
def boms():
    boms = BOM.query.all()
    return render_template('manufacturing/boms.html', boms=boms)

@bp.route('/bom/add', methods=['GET', 'POST'])
@login_required
def add_bom():
    form = BOMForm()
    # Only show manufactured products in the "Finished Product" dropdown
    manufactured_products = Product.query.filter_by(is_manufactured=True).all()
    form.product_id.choices = [(p.id, p.name) for p in manufactured_products]
    
    # All products can be components (except maybe the finished product itself)
    all_products = Product.query.all()

    if form.validate_on_submit():
        bom = BOM(
            name=form.name.data,
            product_id=form.product_id.data,
            labor_cost=form.labor_cost.data or 0,
            overhead_cost=form.overhead_cost.data or 0
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
                    item = BOMItem(
                        bom_id=bom.id,
                        component_id=comp_id,
                        quantity=float(qty),
                        cost=comp_product.cost_price * float(qty)
                    )
                    db.session.add(item)
                    
        # Update total cost of BOM after items are added
        db.session.commit()
        bom.calculate_total_cost()
        
        # Link all available overhead expenses for this product to this BOM
        from app.models import Expense
        db.session.query(Expense).filter(
            Expense.product_id == bom.product_id,
            Expense.is_bom_overhead == True,
            Expense.bom_id == None
        ).update({Expense.bom_id: bom.id}, synchronize_session=False)

        # Update the product's base cost price to reflect the BOM cost
        bom.product.cost_price = bom.total_cost
        db.session.commit()
        
        flash('Bill of Materials created successfully.', 'success')
        return redirect(url_for('manufacturing.boms'))
        
    return render_template('manufacturing/add_bom.html', form=form, all_products=all_products)

@bp.route('/bom/<int:id>')
@login_required
def bom_details(id):
    bom = BOM.query.get_or_404(id)
    return render_template('manufacturing/bom_details.html', bom=bom)

@bp.route('/bom/<int:id>/delete', methods=['POST'])
@login_required
def delete_bom(id):
    bom = BOM.query.get_or_404(id)
    if bom.manufacturing_orders:
        flash('Cannot delete BOM because it has associated Manufacturing Orders.', 'danger')
        return redirect(url_for('manufacturing.boms'))
        
    # Unlink any associated overhead expenses before deleting
    from app.models import Expense
    db.session.query(Expense).filter(Expense.bom_id == id).update({Expense.bom_id: None}, synchronize_session=False)

    db.session.delete(bom)
    db.session.commit()
    flash('BOM deleted successfully.', 'success')
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
    form.bom_id.choices = [(b.id, f"{b.name} ({b.product.name})") for b in boms]
    
    if form.validate_on_submit():
        # Generate Unique Order Number
        today = datetime.utcnow()
        day_str = today.strftime('%Y%m%d')
        prefix = f"MO-{day_str}-"
        
        # Find the highest existing suffix for today
        last_order = ManufacturingOrder.query.filter(
            ManufacturingOrder.order_number.like(f"{prefix}%")
        ).order_by(ManufacturingOrder.order_number.desc()).first()
        
        if last_order:
            try:
                last_suffix = int(last_order.order_number.split('-')[-1])
                new_suffix = last_suffix + 1
            except (ValueError, IndexError):
                new_suffix = 1
        else:
            new_suffix = 1
            
        order_number = f"{prefix}{new_suffix:03d}"
        
        # Final safety loop to avoid any duplicate issues
        while ManufacturingOrder.query.filter_by(order_number=order_number).first():
            new_suffix += 1
            order_number = f"{prefix}{new_suffix:03d}"
        
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
            
        mo.actual_labor_cost = bom.labor_cost * multiplier
        mo.actual_material_cost = sum(item.component.cost_price * (item.quantity * multiplier) for item in bom.items)
        mo.total_cost = mo.actual_labor_cost + mo.actual_material_cost + (bom.overhead_cost * multiplier)
        
        db.session.commit()
        flash('Manufacturing Order created successfully.', 'success')
        return redirect(url_for('manufacturing.orders'))
        
    return render_template('manufacturing/add_order.html', form=form)

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
    # Using estimated BOM labor & overhead for simplicity
    multiplier = order.quantity_to_produce
    order.actual_labor_cost = order.bom.labor_cost * multiplier
    order.total_cost = order.actual_material_cost + order.actual_labor_cost + (order.bom.overhead_cost * multiplier)
    
    # Update standard cost of finished good (Weighted Average or straight replacement based on latest production)
    # Simple replacement for this implementation
    if completed_qty > 0:
        unit_cost = order.total_cost / completed_qty
        finished_good.cost_price = unit_cost
        
    order.status = 'Completed'
    order.end_date = datetime.now().date()
    
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
    total_overhead = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.product_id == id,
        Expense.is_bom_overhead == True,
        Expense.bom_id == None
    ).scalar() or 0
    return jsonify({
        'total_actual_overhead': total_overhead
    })
@bp.route('/order/<int:id>/delete', methods=['POST'])
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

    # Delete the order (cascades will delete MO items)
    db.session.delete(order)
    db.session.commit()
    
    flash(f'Manufacturing Order {order.order_number} deleted and stock changes reversed.', 'success')
    return redirect(url_for('manufacturing.orders'))
