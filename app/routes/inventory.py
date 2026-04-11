from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Product, User, Warehouse
from app.forms import ProductForm
from sqlalchemy import func, inspect
import os
from werkzeug.utils import secure_filename

bp = Blueprint('inventory', __name__)

def has_column(table_name, column_name):
    try:
        inspector = inspect(db.engine)
        return column_name in [c['name'] for c in inspector.get_columns(table_name)]
    except:
        return False

@bp.route('/products')
@login_required
def products():
    category = request.args.get('category', 'all')
    warehouse_id = request.args.get('warehouse_id', '', type=str)
    qty_min = request.args.get('qty_min', '', type=str)
    qty_max = request.args.get('qty_max', '', type=str)
    
    db.session.expire_all()
    query = Product.query
    
    if category != 'all':
        query = query.filter(Product.category == category)
    
    if warehouse_id and warehouse_id.isdigit():
        query = query.filter(Product.warehouse_id == int(warehouse_id))
    
    # Filter by quantity range
    if qty_min and qty_min.isdigit():
        query = query.filter(Product.quantity >= int(qty_min))
    
    if qty_max and qty_max.isdigit():
        query = query.filter(Product.quantity <= int(qty_max))
    
    products = query.order_by(Product.name).all()
    
    # Get all categories for filter
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    # Get all warehouses for filter
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    
    return render_template('inventory/products.html', 
                         products=products, 
                         categories=categories,
                         warehouses=warehouses,
                         current_category=category,
                         current_warehouse_id=warehouse_id,
                         qty_min=qty_min,
                         qty_max=qty_max)

@bp.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    db.session.expire_all()
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    form = ProductForm()
    
    if request.method == 'POST':
        # Manually validate to see what's happening
        if form.name.data and form.sku.data and form.unit_price.data is not None:
            # Check if SKU already exists
            existing_product = Product.query.filter_by(sku=form.sku.data).first()
            if existing_product:
                flash(f'SKU "{form.sku.data}" already exists. Please use a different SKU.', 'error')
                return redirect(url_for('inventory.add_product'))
            
            warehouse_id = request.form.get('warehouse_id')
            product = Product(
                name=form.name.data,
                sku=form.sku.data,
                description=form.description.data,
                unit_price=form.unit_price.data,
                cost_price=form.cost_price.data if form.cost_price.data is not None else 0.0,
                quantity=form.quantity.data,
                reorder_level=form.reorder_level.data,
                category=form.category.data,
                warehouse_id=int(warehouse_id) if warehouse_id and warehouse_id != '0' else None
            )
            
            # Only set is_manufactured if column exists
            if has_column('products', 'is_manufactured'):
                product.is_manufactured = form.is_manufactured.data
            
            # Handle image upload
            if 'image' in request.files:
                image_file = request.files['image']
                if image_file and image_file.filename:
                    filename = secure_filename(image_file.filename)
                    image_path = os.path.join('app', 'static', 'uploads', 'products', filename)
                    os.makedirs(os.path.dirname(image_path), exist_ok=True)
                    image_file.save(image_path)
                    # Normalize path to use forward slashes for consistency
                    product.image_path = image_path.replace('\\', '/')
            
            try:
                db.session.add(product)
                db.session.commit()
                flash('Product added successfully!', 'success')
                return redirect(url_for('inventory.products'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding product: {str(e)}', 'error')
                return redirect(url_for('inventory.add_product'))
        else:
            print(f"Form data: name={form.name.data}, sku={form.sku.data}, unit_price={form.unit_price.data}")
            print(f"Form errors: {form.errors}")
    
    # Fetch unique categories for the dropdown/datalist
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('inventory/add_product.html', form=form, categories=categories, warehouses=warehouses)

@bp.route('/product/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    db.session.expire_all()
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    form = ProductForm(obj=product)
    
    if form.validate_on_submit():
        # Check if SKU is being changed and if the new SKU already exists
        if form.sku.data != product.sku:
            existing_product = Product.query.filter_by(sku=form.sku.data).first()
            if existing_product:
                flash(f'SKU "{form.sku.data}" already exists. Please use a different SKU.', 'error')
                return redirect(url_for('inventory.edit_product', id=product.id))
        
        # Store old cost for versioning check
        old_cost = product.cost_price
        
        warehouse_id = request.form.get('warehouse_id')
        product.name = form.name.data
        product.sku = form.sku.data
        product.description = form.description.data
        product.unit_price = form.unit_price.data
        product.cost_price = form.cost_price.data if form.cost_price.data is not None else 0.0
        product.reorder_level = form.reorder_level.data
        product.category = form.category.data
        product.warehouse_id = int(warehouse_id) if warehouse_id and warehouse_id != '0' else None
        
        # Only set is_manufactured if column exists
        if has_column('products', 'is_manufactured'):
            product.is_manufactured = form.is_manufactured.data
        
        # Handle image upload
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename:
                filename = secure_filename(image_file.filename)
                image_path = os.path.join('app', 'static', 'uploads', 'products', filename)
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                image_file.save(image_path)
                # Normalize path to use forward slashes for consistency
                product.image_path = image_path.replace('\\', '/')
        
        try:
            db.session.commit()
            print(f"\n[DEBUG] Product {product.id} ({product.name}) updated")
            print(f"[DEBUG] Old cost: {old_cost}, New cost: {product.cost_price}")
            print(f"[DEBUG] Costs equal? {old_cost == product.cost_price}")
            
            # Trigger BOM versioning if cost price changed
            if old_cost != product.cost_price:
                print(f"[DEBUG] Cost changed! Triggering BOM versioning...")
                from app.services.bom_versioning import BOMVersioningService
                try:
                    print(f"[DEBUG] Calling check_and_update_bom_for_cost_changes...")
                    # Use current_user.id if available, fallback to admin user
                    user_id = None
                    try:
                        if current_user and current_user.is_authenticated:
                            user_id = current_user.id
                    except (AttributeError, TypeError):
                        pass
                    
                    if user_id is None:
                        # Fallback to admin user
                        admin_user = User.query.filter_by(username='admin').first()
                        user_id = admin_user.id if admin_user else 1
                    
                    updated_boms = BOMVersioningService.check_and_update_bom_for_cost_changes(
                        product_id=product.id,
                        created_by_id=user_id
                    )
                    print(f"[DEBUG] Updated {len(updated_boms)} BOM(s)")
                    if updated_boms:
                        version_count = len(updated_boms)
                        flash(f'Product updated! BOM versions updated for {version_count} BOM(s).', 'info')
                    else:
                        flash('Product updated successfully!', 'success')
                except Exception as e:
                    flash(f'Product updated, but error updating BOM versions: {str(e)}', 'warning')
                    print(f"[DEBUG] Error updating BOM versions: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[DEBUG] Cost did not change, no BOM versioning needed")
                flash('Product updated successfully!', 'success')
            return redirect(url_for('inventory.products'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'error')
            return redirect(url_for('inventory.edit_product', id=product.id))
    
    # Fetch unique categories for the dropdown/datalist
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('inventory/edit_product.html', form=form, product=product, categories=categories, warehouses=warehouses)

@bp.route('/product/<int:id>/delete', methods=['GET', 'POST'])
@login_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    
    # Check if product is associated with any sales, purchases, or stock movements
    if product.sale_items or product.purchase_items or product.stock_movements:
        flash(f'Cannot delete product "{product.name}" because it has associated transaction history (sales, purchases, or stock movements). Try marking it as inactive instead.', 'danger')
        return redirect(url_for('inventory.products'))
        
    try:
        db.session.delete(product)
        db.session.commit()
        flash(f'Product "{product.name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
        
    return redirect(url_for('inventory.products'))

@bp.route('/stock-report')
@login_required
def stock_report():
    products = Product.query.all()
    
    # Calculate statistics
    total_products = len(products)
    total_value = sum(p.quantity * p.cost_price for p in products)
    low_stock_count = sum(1 for p in products if p.quantity <= p.reorder_level)
    out_of_stock = sum(1 for p in products if p.quantity == 0)
    
    return render_template('inventory/stock_report.html',
                         products=products,
                         total_products=total_products,
                         total_value=total_value,
                         low_stock_count=low_stock_count,
                         out_of_stock=out_of_stock)

@bp.route('/api/product/<int:id>')
@login_required
def get_product(id):
    product = Product.query.get_or_404(id)
    return jsonify({
        'id': product.id,
        'name': product.name,
        'sku': product.sku,
        'unit_price': product.unit_price,
        'cost_price': product.cost_price,
        'quantity': product.quantity,
        'reorder_level': product.reorder_level,
        'category': product.category
    })