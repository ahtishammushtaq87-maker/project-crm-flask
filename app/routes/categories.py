from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app import db
from app.models import ProductCategory

bp = Blueprint('categories', __name__)


@bp.route('/categories')
@login_required
def categories():
    search = request.args.get('search', '')
    if search:
        category_list = ProductCategory.query.filter(
            ProductCategory.name.ilike(f'%{search}%')
        ).order_by(ProductCategory.name).all()
    else:
        category_list = ProductCategory.query.order_by(ProductCategory.name).all()
    return render_template('categories/index.html', categories=category_list, search=search)


@bp.route('/category/create', methods=['GET', 'POST'])
@login_required
def create_category():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('Category name is required.', 'error')
            return redirect(url_for('categories.create_category'))
        
        existing = ProductCategory.query.filter_by(name=name).first()
        if existing:
            flash(f'Category "{name}" already exists.', 'error')
            return redirect(url_for('categories.create_category'))
        
        category = ProductCategory(
            name=name,
            description=description
        )
        
        try:
            db.session.add(category)
            db.session.commit()
            flash('Category created successfully!', 'success')
            return redirect(url_for('categories.categories'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating category: {str(e)}', 'error')
    
    return render_template('categories/create.html')


@bp.route('/category/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    category = ProductCategory.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('Category name is required.', 'error')
            return redirect(url_for('categories.edit_category', id=id))
        
        existing = ProductCategory.query.filter(
            ProductCategory.name == name,
            ProductCategory.id != id
        ).first()
        if existing:
            flash(f'Category "{name}" already exists.', 'error')
            return redirect(url_for('categories.edit_category', id=id))
        
        category.name = name
        category.description = description
        
        try:
            db.session.commit()
            flash('Category updated successfully!', 'success')
            return redirect(url_for('categories.categories'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating category: {str(e)}', 'error')
    
    return render_template('categories/edit.html', category=category)


@bp.route('/category/<int:id>/delete', methods=['POST'])
@login_required
def delete_category(id):
    category = ProductCategory.query.get_or_404(id)
    
    if category.products:
        flash(f'Cannot delete category "{category.name}" because it has {len(category.products)} associated products. Please reassign products first.', 'error')
        return redirect(url_for('categories.categories'))
    
    try:
        db.session.delete(category)
        db.session.commit()
        flash(f'Category "{category.name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting category: {str(e)}', 'error')
    
    return redirect(url_for('categories.categories'))


@bp.route('/api/categories')
@login_required
def api_categories():
    categories = ProductCategory.query.filter_by(is_active=True).order_by(ProductCategory.name).all()
    return jsonify([{'id': c.id, 'name': c.name} for c in categories])


@bp.route('/api/category/<int:id>')
@login_required
def api_category(id):
    category = ProductCategory.query.get_or_404(id)
    return jsonify({
        'id': category.id,
        'name': category.name,
        'description': category.description,
        'is_active': category.is_active
    })