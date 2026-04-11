from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Warehouse, Product
from sqlalchemy import func

bp = Blueprint('warehouse', __name__)

@bp.route('/warehouses')
@login_required
def warehouses():
    search = request.args.get('search', '')
    query = Warehouse.query
    if search:
        query = query.filter(
            (Warehouse.name.ilike(f'%{search}%')) | 
            (Warehouse.code.ilike(f'%{search}%'))
        )
    warehouses = query.order_by(Warehouse.name).all()
    return render_template('warehouse/warehouses.html', warehouses=warehouses)

@bp.route('/warehouse/add', methods=['GET', 'POST'])
@login_required
def add_warehouse():
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        address = request.form.get('address')
        city = request.form.get('city')
        phone = request.form.get('phone')
        email = request.form.get('email')
        manager = request.form.get('manager')
        
        existing = Warehouse.query.filter_by(code=code).first()
        if existing:
            flash(f'Warehouse code "{code}" already exists.', 'error')
            return redirect(url_for('warehouse.add_warehouse'))
        
        warehouse = Warehouse(
            name=name,
            code=code,
            address=address,
            city=city,
            phone=phone,
            email=email,
            manager=manager
        )
        try:
            db.session.add(warehouse)
            db.session.commit()
            flash(f'Warehouse "{name}" created successfully!', 'success')
            return redirect(url_for('warehouse.warehouses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating warehouse: {str(e)}', 'error')
    
    return render_template('warehouse/add_warehouse.html')

@bp.route('/warehouse/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_warehouse(id):
    warehouse = Warehouse.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        address = request.form.get('address')
        city = request.form.get('city')
        phone = request.form.get('phone')
        email = request.form.get('email')
        manager = request.form.get('manager')
        is_active = request.form.get('is_active') == 'on'
        
        existing = Warehouse.query.filter(Warehouse.code == code, Warehouse.id != id).first()
        if existing:
            flash(f'Warehouse code "{code}" already exists.', 'error')
            return redirect(url_for('warehouse.edit_warehouse', id=id))
        
        warehouse.name = name
        warehouse.code = code
        warehouse.address = address
        warehouse.city = city
        warehouse.phone = phone
        warehouse.email = email
        warehouse.manager = manager
        warehouse.is_active = is_active
        
        try:
            db.session.commit()
            flash('Warehouse updated successfully!', 'success')
            return redirect(url_for('warehouse.warehouses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating warehouse: {str(e)}', 'error')
    
    return render_template('warehouse/edit_warehouse.html', warehouse=warehouse)

@bp.route('/warehouse/<int:id>')
@login_required
def warehouse_detail(id):
    warehouse = Warehouse.query.get_or_404(id)
    products = Product.query.filter_by(warehouse_id=id).order_by(Product.name).all()
    
    total_quantity = sum(p.quantity for p in products)
    total_value = sum(p.quantity * p.cost_price for p in products)
    total_items = len(products)
    
    return render_template('warehouse/warehouse_detail.html', 
                         warehouse=warehouse, 
                         products=products,
                         total_quantity=total_quantity,
                         total_value=total_value,
                         total_items=total_items)

@bp.route('/warehouse/<int:id>/delete', methods=['POST'])
@login_required
def delete_warehouse(id):
    warehouse = Warehouse.query.get_or_404(id)
    
    if warehouse.products:
        flash('Cannot delete warehouse with associated products. Remove or reassign products first.', 'error')
        return redirect(url_for('warehouse.warehouse_detail', id=id))
    
    try:
        db.session.delete(warehouse)
        db.session.commit()
        flash('Warehouse deleted successfully!', 'success')
        return redirect(url_for('warehouse.warehouses'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting warehouse: {str(e)}', 'error')
        return redirect(url_for('warehouse.warehouse_detail', id=id))

@bp.route('/api/warehouses')
@login_required
def api_warehouses():
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    return jsonify([{'id': w.id, 'name': w.name, 'code': w.code} for w in warehouses])

@bp.route('/api/warehouses/<int:id>/summary')
@login_required
def api_warehouse_summary(id):
    warehouse = Warehouse.query.get_or_404(id)
    products = Product.query.filter_by(warehouse_id=id).all()
    
    return jsonify({
        'id': warehouse.id,
        'name': warehouse.name,
        'code': warehouse.code,
        'total_products': len(products),
        'total_quantity': sum(p.quantity for p in products),
        'total_value': sum(p.quantity * p.cost_price for p in products)
    })