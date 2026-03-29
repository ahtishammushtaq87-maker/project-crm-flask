from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app import db
from app.models import Product
from app.forms import ProductForm
from sqlalchemy import func
import os
from werkzeug.utils import secure_filename

bp = Blueprint('inventory', __name__)

@bp.route('/products')
@login_required
def products():
    category = request.args.get('category', 'all')
    qty_min = request.args.get('qty_min', '', type=str)
    qty_max = request.args.get('qty_max', '', type=str)
    
    query = Product.query
    
    if category != 'all':
        query = query.filter(Product.category == category)
    
    # Filter by quantity range
    if qty_min and qty_min.isdigit():
        query = query.filter(Product.quantity >= int(qty_min))
    
    if qty_max and qty_max.isdigit():
        query = query.filter(Product.quantity <= int(qty_max))
    
    products = query.order_by(Product.name).all()
    
    # Get all categories for filter
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('inventory/products.html', 
                         products=products, 
                         categories=categories,
                         current_category=category,
                         qty_min=qty_min,
                         qty_max=qty_max)

@bp.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        # Check if SKU already exists
        existing_product = Product.query.filter_by(sku=form.sku.data).first()
        if existing_product:
            flash(f'SKU "{form.sku.data}" already exists. Please use a different SKU.', 'error')
            return redirect(url_for('inventory.add_product'))
        
        product = Product(
            name=form.name.data,
            sku=form.sku.data,
            description=form.description.data,
            unit_price=form.unit_price.data,
            cost_price=form.cost_price.data,
            quantity=form.quantity.data,
            reorder_level=form.reorder_level.data,
            category=form.category.data
        )
        
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
    
    # Fetch unique categories for the dropdown/datalist
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('inventory/add_product.html', form=form, categories=categories)

@bp.route('/product/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    form = ProductForm(obj=product)
    
    if form.validate_on_submit():
        # Check if SKU is being changed and if the new SKU already exists
        if form.sku.data != product.sku:
            existing_product = Product.query.filter_by(sku=form.sku.data).first()
            if existing_product:
                flash(f'SKU "{form.sku.data}" already exists. Please use a different SKU.', 'error')
                return redirect(url_for('inventory.edit_product', id=product.id))
        
        product.name = form.name.data
        product.sku = form.sku.data
        product.description = form.description.data
        product.unit_price = form.unit_price.data
        product.cost_price = form.cost_price.data
        product.reorder_level = form.reorder_level.data
        product.category = form.category.data
        
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
            flash('Product updated successfully!', 'success')
            return redirect(url_for('inventory.products'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'error')
            return redirect(url_for('inventory.edit_product', id=product.id))
    
    # Fetch unique categories for the dropdown/datalist
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('inventory/edit_product.html', form=form, product=product, categories=categories)

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