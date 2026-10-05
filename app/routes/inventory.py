from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.utils import permission_required, log_activity
from app import db
from app.models import (
    Product, User, Warehouse, ProductCategory, Unit, ProductWarehouseStock,
    SaleItem, SaleReturnItem, PurchaseItem, PurchaseReturnItem,
    ToolReceivingItem, ToolDeliveringItem, StockMovement, ActivityLog,
    Sale, SaleReturn, PurchaseBill, PurchaseReturn, ToolReceiving, ToolDelivering,
    BillReceiveItem, Vendor, ProductStructureFile
)
from app.forms import ProductForm, UnitForm
from sqlalchemy import func, inspect
from datetime import datetime
import os
import json
from io import BytesIO
from werkzeug.utils import secure_filename
from app.routes.filters import apply_saved_filter_to_query

bp = Blueprint('inventory', __name__)

def has_column(table_name, column_name):
    try:
        inspector = inspect(db.engine)
        return column_name in [c['name'] for c in inspector.get_columns(table_name)]
    except:
        return False


def _delete_product_image_file_if_unshared(product):
    """Removes product.image_path's file from disk, UNLESS some other
    Product row still points at that same path - which can only happen
    for a product whose image collided with another's before uploads were
    given unique filenames (see edit_product/add_product). Deleting a
    still-shared file would silently break the other product's image too,
    so this checks first rather than ever assuming a path is exclusively
    owned by the product row it's being deleted from."""
    path = product.image_path
    if not path or not os.path.exists(path):
        return
    other_owner = Product.query.filter(Product.image_path == path, Product.id != product.id).first()
    if other_owner:
        return
    try:
        os.remove(path)
    except OSError:
        pass

# Item Structure files (any type) live OUTSIDE app/static so they are never
# publicly reachable - they are only served by product_structure_file(),
# which requires login.
STRUCTURE_UPLOAD_DIR = os.path.join('app', 'uploads', 'product_structure')

# Only these are ever rendered inline in the browser; everything else is
# forced to download (an uploaded .html/.svg must never execute in our origin).
_STRUCTURE_INLINE_TYPES = {
    'pdf': 'application/pdf',
    'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
    'gif': 'image/gif', 'webp': 'image/webp', 'bmp': 'image/bmp',
    'txt': 'text/plain', 'csv': 'text/plain', 'log': 'text/plain',
    'md': 'text/plain', 'json': 'text/plain', 'xml': 'text/plain',
}


def _save_structure_files(product):
    """Save every file posted as `structure_files` for this product.
    Returns the list of disk paths written (so a caller can clean up if the
    DB commit then fails)."""
    import mimetypes, time, uuid
    saved = []
    files = [f for f in request.files.getlist('structure_files') if f and f.filename]
    if not files:
        return saved
    folder = os.path.join(STRUCTURE_UPLOAD_DIR, str(product.id))
    os.makedirs(folder, exist_ok=True)
    for f in files:
        original = os.path.basename(f.filename.replace('\\', '/'))[:255] or 'file'
        safe = secure_filename(original) or 'file'
        if '.' not in safe and '.' in original:
            safe += '.' + (secure_filename(original.rsplit('.', 1)[-1]) or 'bin')
        path = os.path.join(folder, f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{safe}")
        f.save(path)
        saved.append(path)
        db.session.add(ProductStructureFile(
            product_id=product.id,
            original_name=original,
            stored_path=path.replace('\\', '/'),
            mime_type=(mimetypes.guess_type(original)[0] or f.mimetype or 'application/octet-stream')[:150],
            file_size=os.path.getsize(path),
            uploaded_by=current_user.id if current_user.is_authenticated else None,
        ))
    return saved


def _remove_files_from_disk(paths):
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def _structure_counts():
    """{product_id: number of Item Structure files} in one query."""
    rows = db.session.query(ProductStructureFile.product_id, func.count(ProductStructureFile.id)) \
        .group_by(ProductStructureFile.product_id).all()
    return dict(rows)


def _vendor_choices(current_vendor_id=None):
    """Active vendors for the product form's Vendor dropdown. The product's
    currently linked vendor is re-included even if it has since been
    deactivated, so editing an old product never silently drops it."""
    vendors = Vendor.query.filter_by(is_active=True).order_by(Vendor.name).all()
    if current_vendor_id and not any(v.id == current_vendor_id for v in vendors):
        current = Vendor.query.get(current_vendor_id)
        if current:
            vendors.append(current)
    return vendors


def _parse_vendor_id(raw):
    return int(raw) if raw and raw.isdigit() and raw != '0' else None


@bp.route('/products')
@login_required
def products():
    category = request.args.get('category', 'all')
    sku_filter = request.args.get('sku', '', type=str)
    warehouse_id = request.args.get('warehouse_id', '', type=str)
    qty_min = request.args.get('qty_min', '', type=str)
    qty_max = request.args.get('qty_max', '', type=str)
    search_query = request.args.get('search', '', type=str).strip()
    
    db.session.expire_all()
    query = Product.query
    
    # Search filter
    if search_query:
        query = query.filter(
            (Product.name.ilike(f'%{search_query}%')) | 
            (Product.sku.ilike(f'%{search_query}%'))
        )

    # SKU direct filter
    if sku_filter:
        query = query.filter(Product.sku == sku_filter)
    
    if category != 'all':
        query = query.filter(Product.category_id == int(category))
    
    if warehouse_id and warehouse_id.isdigit():
        wh_id = int(warehouse_id)
        from app.models import ProductWarehouseStock
        # Find products that have stock in this warehouse either in the bridge table or the legacy field
        subquery = db.session.query(ProductWarehouseStock.product_id).filter(
            ProductWarehouseStock.warehouse_id == wh_id,
            ProductWarehouseStock.quantity > 0
        )
        query = query.filter(
            (Product.id.in_(subquery)) | (Product.warehouse_id == wh_id)
        )
    
    # Filter by quantity range
    if qty_min and qty_min.isdigit():
        query = query.filter(Product.quantity >= int(qty_min))
    
    if qty_max and qty_max.isdigit():
        query = query.filter(Product.quantity <= int(qty_max))
    
    query = apply_saved_filter_to_query(query, 'product', request.args)

    products = query.order_by(Product.name).all()
    
    # Get all categories for filter
    categories = ProductCategory.query.filter_by(is_active=True).order_by(ProductCategory.name).all()
    
    # Get all warehouses for filter
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    
    # Get all products for SKU search dropdown
    all_products_for_sku = Product.query.with_entities(Product.sku, Product.name).order_by(Product.sku).all()
    
    return render_template('inventory/products.html', 
                         products=products, 
                         categories=categories,
                         warehouses=warehouses,
                         all_products_for_sku=all_products_for_sku,
                         structure_counts=_structure_counts(),
                         current_category=category,
                         current_sku=sku_filter,
                         current_warehouse_id=warehouse_id,
                         qty_min=qty_min,
                         qty_max=qty_max,
                         search_query=search_query,
                         active_module='product',
                         filter_id=request.args.get('filter_id'))

@bp.route('/product/add', methods=['GET', 'POST'])
@login_required
@permission_required('inventory', action='add')
def add_product():
    db.session.expire_all()
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    form = ProductForm()
    
    if request.method == 'POST':
        # Get form data directly from request
        name = request.form.get('name')
        sku = request.form.get('sku')
        description = request.form.get('description')
        unit_price = request.form.get('unit_price')
        cost_price = request.form.get('cost_price')
        quantity = request.form.get('quantity')
        unit = request.form.get('unit')
        reorder_level = request.form.get('reorder_level')
        category_id = request.form.get('category_id')
        is_manufactured = 'is_manufactured' in request.form
        finished_good_price = request.form.get('finished_good_price')

        # Auto SKU from the category's SKU structure (e.g. 1010 -> 1010001).
        # Blank SKU -> generate; an auto SKU taken by someone else meanwhile
        # -> move on to the next free number instead of rejecting the form.
        sku = (sku or '').strip()
        category = ProductCategory.query.get(int(category_id)) if category_id and category_id.isdigit() and category_id != '0' else None
        if category and category.sku_prefix:
            if not sku:
                sku = category.next_sku()
            elif sku.startswith(category.sku_prefix) and Product.query.filter_by(sku=sku).first():
                new_sku = category.next_sku()
                flash(f'SKU "{sku}" was just taken, so this item was given SKU "{new_sku}".', 'info')
                sku = new_sku

        # Validate required fields
        if name and sku and unit_price is not None:
            # Check if SKU already exists
            existing_product = Product.query.filter_by(sku=sku).first()
            if existing_product:
                flash(f'SKU "{sku}" already exists. Please use a different SKU.', 'error')
                return redirect(url_for('inventory.add_product'))
            
            warehouse_id = request.form.get('warehouse_id')
            # If finished good, use finished_good_price as the selling price
            if is_manufactured and finished_good_price:
                final_unit_price = float(finished_good_price)
            else:
                final_unit_price = float(unit_price)
            
            product = Product(
                name=name,
                sku=sku,
                description=description,
                unit_price=final_unit_price,
                cost_price=float(cost_price) if cost_price else 0.0,
                quantity=float(quantity) if quantity else 0,
                unit=unit,
                reorder_level=float(reorder_level) if reorder_level else 0,
                category_id=int(category_id) if category_id and category_id != '0' else None,
                warehouse_id=int(warehouse_id) if warehouse_id and warehouse_id != '0' else None,
                vendor_id=_parse_vendor_id(request.form.get('vendor_id')),
                location=(request.form.get('location') or '').strip()[:100] or None
            )
            
            product.is_manufactured = is_manufactured
            product.finished_good_price = float(finished_good_price) if finished_good_price else None
            
            # Handle image upload
            if 'image' in request.files:
                image_file = request.files['image']
                if image_file and image_file.filename:
                    # Prefix with a timestamp+uuid so two products whose
                    # uploaded files happen to share the same original name
                    # (e.g. "IMG_20240501.jpg" from a phone) never collide on
                    # disk - a plain secure_filename() would silently
                    # overwrite the earlier product's file and make both
                    # products show whichever image was uploaded last. Same
                    # convention as bill image uploads (see add_expense).
                    import time, uuid
                    original_filename = secure_filename(image_file.filename)
                    unique_prefix = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
                    filename = f"{unique_prefix}_{original_filename}"
                    image_path = os.path.join('app', 'static', 'uploads', 'products', filename)
                    os.makedirs(os.path.dirname(image_path), exist_ok=True)
                    image_file.save(image_path)
                    product.image_path = image_path.replace('\\', '/')
            
            structure_paths = []
            try:
                db.session.add(product)
                db.session.flush() # Get product ID
                structure_paths = _save_structure_files(product)
                
                # Sync with ProductWarehouseStock
                if product.warehouse_id and product.quantity > 0:
                    from app.models import ProductWarehouseStock
                    wh_stock = ProductWarehouseStock(
                        product_id=product.id,
                        warehouse_id=product.warehouse_id,
                        quantity=product.quantity
                    )
                    db.session.add(wh_stock)
                
                db.session.commit()
                
                log_activity('Inventory', f'Added Product: {product.name}', 
                            f'SKU: {product.sku}, Qty: {product.quantity}, Price: {product.unit_price}')
                
                flash('Product added successfully!', 'success')
                return redirect(url_for('inventory.products'))
            except Exception as e:
                db.session.rollback()
                _remove_files_from_disk(structure_paths)
                flash(f'Error adding product: {str(e)}', 'error')
                return redirect(url_for('inventory.add_product'))
        else:
            flash('Please fill in all required fields.', 'error')
    
    # Fetch categories for the dropdown
    categories = ProductCategory.query.filter_by(is_active=True).order_by(ProductCategory.name).all()
    units = Unit.query.filter_by(is_active=True).order_by(Unit.name).all()
    
    return render_template('inventory/add_product.html', form=form, categories=categories, warehouses=warehouses, units=units,
                           vendors=_vendor_choices())


@bp.route('/product/<int:id>/structure')
@login_required
def product_structure(id):
    """Gallery of every Item Structure file for a product, with previews."""
    product = Product.query.get_or_404(id)
    return render_template('inventory/product_structure.html', product=product,
                           files=product.structure_files)


@bp.route('/product/structure-file/<int:file_id>')
@login_required
def product_structure_file(file_id):
    """Serve one Item Structure file. PDFs/images/text open inline (for the
    previews); any other type - and ?download=1 - is sent as an attachment."""
    from flask import send_file, abort
    sf = ProductStructureFile.query.get_or_404(file_id)
    root = os.path.abspath(STRUCTURE_UPLOAD_DIR)
    path = os.path.abspath(sf.stored_path)
    if not path.startswith(root + os.sep) or not os.path.exists(path):
        abort(404)
    inline_type = _STRUCTURE_INLINE_TYPES.get(sf.extension)
    as_download = request.args.get('download') == '1' or not inline_type
    response = send_file(
        path,
        mimetype=inline_type or sf.mime_type or 'application/octet-stream',
        as_attachment=as_download,
        download_name=sf.original_name,
        max_age=0,
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@bp.route('/product/<int:id>/info-pdf')
@login_required
def product_info_pdf(id):
    """Item Information PDF (opened inline in a new tab from the Products
    list actions menu)."""
    from flask import make_response
    from app.models import Company
    from app.pdf_utils import generate_product_info_pdf

    product = Product.query.get_or_404(id)
    try:
        buffer = generate_product_info_pdf(product, Company.query.first(),
                                           generated_by=getattr(current_user, 'username', None))
    except Exception as e:
        flash(f'Could not generate the item information PDF: {str(e)}', 'error')
        return redirect(url_for('inventory.products'))

    safe_sku = secure_filename(product.sku or '') or f'item-{product.id}'
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename="Item_Info_{safe_sku}.pdf"'
    return response


@bp.route('/product/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('inventory', action='edit')
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
        
        product.is_manufactured = form.is_manufactured.data if form.is_manufactured.data else False
        
        # Handle finished_good_price
        finished_good_price = request.form.get('finished_good_price')
        product.finished_good_price = float(finished_good_price) if finished_good_price else None
        
        # If finished good, use finished_good_price as the selling price
        if product.is_manufactured and product.finished_good_price:
            product.unit_price = product.finished_good_price
        else:
            product.unit_price = form.unit_price.data
        
        product.cost_price = form.cost_price.data if form.cost_price.data is not None else 0.0
        product.unit = request.form.get('unit')
        product.reorder_level = form.reorder_level.data
        category_id = request.form.get('category_id')
        product.category_id = int(category_id) if category_id and category_id != '0' else None
        product.warehouse_id = int(warehouse_id) if warehouse_id and warehouse_id != '0' else None
        product.vendor_id = _parse_vendor_id(request.form.get('vendor_id'))
        product.location = (request.form.get('location') or '').strip()[:100] or None
        
        # Handle quantity update
        quantity = request.form.get('quantity')
        if quantity is not None:
            try:
                product.quantity = float(quantity)
            except (ValueError, TypeError):
                pass
        
        # Handle image deletion or upload
        remove_image = request.form.get('remove_image') == '1'
        
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename:
                # Prefix with a timestamp+uuid so two products whose
                # uploaded files happen to share the same original name
                # (e.g. "IMG_20240501.jpg" from a phone) never collide on
                # disk - a plain secure_filename() would silently save the
                # new upload over the OLD file, which is exactly what made
                # unrelated products' images change together before: if two
                # products' image_path had ever pointed at the same
                # filename, editing either one's image overwrote the file
                # both were reading from. Same convention as bill image
                # uploads (see add_expense).
                import time, uuid
                original_filename = secure_filename(image_file.filename)
                unique_prefix = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
                filename = f"{unique_prefix}_{original_filename}"
                image_path = os.path.join('app', 'static', 'uploads', 'products', filename)
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                image_file.save(image_path)

                # Only NOW that the new file is safely saved under its own
                # unique name, remove the old one - _delete_product_image_
                # file_if_unshared() skips it if another product still
                # points at that same path (an older collision left shared).
                _delete_product_image_file_if_unshared(product)

                product.image_path = image_path.replace('\\', '/')
            elif remove_image and product.image_path:
                # No new image but remove_image requested
                _delete_product_image_file_if_unshared(product)
                product.image_path = None
        elif remove_image and product.image_path:
            # remove_image requested and image existed
            _delete_product_image_file_if_unshared(product)
            product.image_path = None
        
        try:
            # Sync with ProductWarehouseStock if warehouse_id is set
            if product.warehouse_id:
                from app.models import ProductWarehouseStock
                wh_stock = ProductWarehouseStock.query.filter_by(
                    product_id=product.id,
                    warehouse_id=product.warehouse_id
                ).first()
                if not wh_stock:
                    wh_stock = ProductWarehouseStock(
                        product_id=product.id,
                        warehouse_id=product.warehouse_id,
                        quantity=0.0
                    )
                    db.session.add(wh_stock)
                
                # If quantity was also updated, we need to decide how to sync.
                # In standard inventory edit, we usually set the TOTAL quantity.
                # To be safe, we'll set this warehouse's stock to the new total IF it was the only warehouse,
                # but if there are multiple, it's ambiguous. 
                # For now, let's just make sure a record exists.
                # If the user is specifically editing the "Primary" warehouse quantity:
                wh_stock.quantity = product.quantity

            _save_warehouse_costs(product)

            # Item Structure: remove the files the user marked, then add new ones
            removed_paths = []
            delete_ids = {int(x) for x in request.form.getlist('delete_structure_ids') if x.isdigit()}
            for sf in list(product.structure_files):
                if sf.id in delete_ids:
                    removed_paths.append(sf.stored_path)
                    db.session.delete(sf)
            _save_structure_files(product)

            db.session.commit()
            _remove_files_from_disk(removed_paths)
            
            log_activity('Inventory', f'Updated Product: {product.name}', 
                        f'SKU: {product.sku}, New Qty: {product.quantity}, New Price: {product.unit_price}')
            
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
    
    # Fetch categories for the dropdown
    categories = ProductCategory.query.filter_by(is_active=True).order_by(ProductCategory.name).all()
    units = Unit.query.filter_by(is_active=True).order_by(Unit.name).all()
    
    return render_template('inventory/edit_product.html', form=form, product=product, categories=categories, warehouses=warehouses, units=units,
                           vendors=_vendor_choices(product.vendor_id),
                           warehouse_cost_rows=_warehouse_cost_rows(product, warehouses))


def _warehouse_cost_rows(product, warehouses):
    """One row per warehouse for the item's 'Cost by Warehouse' table: active
    warehouses plus any other warehouse that has a stock row for it."""
    from app.models import ProductWarehouseStock
    rows = {r.warehouse_id: r for r in ProductWarehouseStock.query.filter_by(product_id=product.id).all()}
    whs = list(warehouses)
    known = {w.id for w in whs}
    for wid, r in rows.items():
        if wid not in known and r.warehouse:
            whs.append(r.warehouse)
    # Latest transfer INTO each warehouse for this item: shows how its cost was
    # built (source cost + this warehouse's share of the shipping, per unit).
    from app.models import WarehouseTransfer, WarehouseTransferItem
    last_in = {}
    items = (WarehouseTransferItem.query.join(WarehouseTransfer)
             .filter(WarehouseTransferItem.product_id == product.id)
             .order_by(WarehouseTransfer.date.desc(), WarehouseTransfer.id.desc()).all())
    for it in items:
        last_in.setdefault(it.transfer.to_warehouse_id, it)

    out = []
    for wh in whs:
        r = rows.get(wh.id)
        if r:
            qty = r.quantity or 0
        else:  # legacy: all stock implicitly in Product.warehouse_id
            qty = (product.quantity or 0) if (not rows and product.warehouse_id == wh.id) else 0
        out.append({'warehouse': wh, 'quantity': qty, 'own_cost': r.cost_price if r else None,
                    'last_transfer': last_in.get(wh.id)})
    out.sort(key=lambda x: (-(x['quantity'] > 0), x['warehouse'].name))
    return out


def _save_warehouse_costs(product):
    """Save the 'Cost by Warehouse' inputs: a number gives that warehouse its
    own cost, blank makes it follow the item's normal cost again."""
    if not request.form.get('wh_costs_present'):
        return
    from app.models import ProductWarehouseStock
    from app.services import warehouse_cost
    for key, raw in request.form.items():
        if not key.startswith('wh_cost_'):
            continue
        try:
            wh_id = int(key[len('wh_cost_'):])
        except ValueError:
            continue
        raw = (raw or '').strip()
        row = ProductWarehouseStock.query.filter_by(product_id=product.id, warehouse_id=wh_id).first()
        if raw == '':
            if row and row.cost_price is not None:
                row.cost_price = None
            continue
        try:
            value = max(float(raw), 0.0)
        except ValueError:
            continue
        if row and row.cost_price is not None and abs(row.cost_price - value) < 0.005:
            continue  # unchanged (the input shows it rounded to 2 decimals)
        if not row and not Warehouse.query.get(wh_id):
            continue
        warehouse_cost.set_cost(product, wh_id, value)

@bp.route('/product/<int:id>/delete', methods=['GET', 'POST'])
@login_required
@permission_required('inventory', action='delete')
def delete_product(id):
    product = Product.query.get_or_404(id)
    
    # Check if product is associated with any sales, purchases, or stock movements
    if product.sale_items or product.purchase_items or product.stock_movements:
        flash(f'Cannot delete product "{product.name}" because it has associated transaction history (sales, purchases, or stock movements). Try marking it as inactive instead.', 'danger')
        return redirect(url_for('inventory.products'))
        
    try:
        structure_paths = [sf.stored_path for sf in product.structure_files]
        db.session.delete(product)
        db.session.commit()
        _remove_files_from_disk(structure_paths)
        
        log_activity('Inventory', f'Deleted Product: {product.name}', f'SKU: {product.sku}')
        
        flash(f'Product "{product.name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')

    return redirect(url_for('inventory.products'))

@bp.route('/product/<int:id>/toggle-obsolete', methods=['POST'])
@login_required
def toggle_obsolete_product(id):
    """Admin-only: flip Product.is_obsolete. Marking a product obsolete
    hides it from "pick a product" dropdowns used to create new records
    elsewhere in the app (Sales, Purchase, BOM, Manufacturing, Production
    Targets, Expenses, Tools, Product Development) - it never removes the
    product itself, never touches stock/cost, and every existing record
    that already references it keeps displaying and editing normally."""
    if current_user.role != 'admin':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Only an admin can obsolete or un-obsolete a product.'}), 403
        flash('Only an admin can obsolete or un-obsolete a product.', 'danger')
        return redirect(url_for('inventory.products'))

    product = Product.query.get_or_404(id)

    if product.is_obsolete:
        product.is_obsolete = False
        product.obsoleted_at = None
        product.obsoleted_by = None
        state = 'active'
        message = f'"{product.name}" is no longer obsolete - it is available again in item pickers.'
    else:
        product.is_obsolete = True
        product.obsoleted_at = datetime.utcnow()
        product.obsoleted_by = current_user.id
        state = 'obsolete'
        message = f'"{product.name}" is now marked Obsolete - it will no longer appear in item pickers for new records.'

    db.session.commit()
    log_activity('Inventory', f'Product set {state}: {product.name}', f'SKU: {product.sku}')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': message, 'is_obsolete': product.is_obsolete})

    flash(message, 'success')
    return redirect(url_for('inventory.products'))

@bp.route('/products/bulk-delete', methods=['POST'])
@login_required
@permission_required('inventory', action='delete')
def bulk_delete_products():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'message': 'No products selected'}), 400
    
    deleted_count = 0
    skipped_count = 0
    errors = []
    structure_paths = []
    
    for product_id in ids:
        product = Product.query.get(product_id)
        if not product:
            continue
            
        # Check if product is associated with any sales, purchases, or stock movements
        if product.sale_items or product.purchase_items or product.stock_movements:
            skipped_count += 1
            continue
            
        try:
            structure_paths += [sf.stored_path for sf in product.structure_files]
            db.session.delete(product)
            deleted_count += 1
        except Exception as e:
            db.session.rollback()
            errors.append(f'Error deleting {product.name}: {str(e)}')
            
    if deleted_count > 0:
        db.session.commit()
        _remove_files_from_disk(structure_paths)
        
    message = f'Successfully deleted {deleted_count} products.'
    if skipped_count > 0:
        message += f' Skipped {skipped_count} products with transaction history.'
    
    if errors:
        return jsonify({'success': False, 'message': message, 'errors': errors}), 500
        
    return jsonify({'success': True, 'message': message})

@bp.route('/products/bulk-assign-warehouse', methods=['POST'])
@login_required
@permission_required('inventory', action='edit')
def bulk_assign_warehouse():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])
    warehouse_id = data.get('warehouse_id')

    if not ids:
        return jsonify({'success': False, 'message': 'No products selected'}), 400

    if not warehouse_id:
        return jsonify({'success': False, 'message': 'No warehouse selected'}), 400

    if warehouse_id == 'none':
        updated_count = 0
        skipped_count = 0
        for product_id in ids:
            product = Product.query.get(product_id)
            if product:
                product.warehouse_id = None
                updated_count += 1
            else:
                skipped_count += 1
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Successfully unassigned warehouse from {updated_count} product(s).'})

    # Convert warehouse_id to int safely
    try:
        warehouse_id = int(warehouse_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid warehouse ID'}), 400

    # Verify warehouse exists
    warehouse = Warehouse.query.get(warehouse_id)
    if not warehouse:
        return jsonify({'success': False, 'message': 'Warehouse not found'}), 400

    updated_count = 0
    skipped_count = 0
    errors = []

    for product_id in ids:
        try:
            pid = int(product_id)
        except (ValueError, TypeError):
            skipped_count += 1
            continue

        product = Product.query.get(pid)
        if not product:
            skipped_count += 1
            continue

        try:
            # Update the legacy warehouse_id on product
            product.warehouse_id = warehouse_id

            # Also upsert into the ProductWarehouseStock bridge table
            # so warehouse-based stock tracking works correctly
            wh_stock = ProductWarehouseStock.query.filter_by(
                product_id=pid,
                warehouse_id=warehouse_id
            ).first()
            if not wh_stock:
                wh_stock = ProductWarehouseStock(
                    product_id=pid,
                    warehouse_id=warehouse_id,
                    quantity=product.quantity or 0
                )
                db.session.add(wh_stock)
            # (if already exists, leave the existing quantity untouched)

            updated_count += 1
        except Exception as e:
            errors.append(f'Error updating {product.name}: {str(e)}')

    if updated_count > 0:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500

    message = f'Successfully assigned "{warehouse.name}" to {updated_count} product(s).'
    if skipped_count > 0:
        message += f' {skipped_count} product(s) could not be found and were skipped.'

    if errors:
        return jsonify({'success': False, 'message': message, 'errors': errors}), 500

    return jsonify({'success': True, 'message': message})


@bp.route('/stock-report')
@login_required
def stock_report():
    query = Product.query
    query = apply_saved_filter_to_query(query, 'product', request.args)
    products = query.all()
    
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
                         out_of_stock=out_of_stock,
                         active_module='product',
                         filter_id=request.args.get('filter_id'))

@bp.route('/product/bulk-upload', methods=['GET', 'POST'])
@login_required
@permission_required('inventory', action='add')
def bulk_upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('inventory.bulk_upload'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('inventory.bulk_upload'))
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('Please upload an Excel file (.xlsx or .xls)', 'error')
            return redirect(url_for('inventory.bulk_upload'))
        
        try:
            from openpyxl import load_workbook
            from io import BytesIO
            file_content = file.read()
            wb = load_workbook(filename=BytesIO(file_content), read_only=True)
            ws = wb.active
            rows = list(ws.values)
            if not rows:
                flash('File is empty', 'error')
                return redirect(url_for('inventory.bulk_upload'))
            headers = [str(h) if h else '' for h in rows[0]]
            
            required_columns = ['name', 'sku']
            missing = [col for col in required_columns if col not in headers]
            if missing:
                flash(f'Missing required columns: {", ".join(missing)}', 'error')
                return redirect(url_for('inventory.bulk_upload'))
            
            added = 0
            errors = []
            
            for idx, row in enumerate(rows[1:], start=2):
                try:
                    row_dict = {}
                    for i, val in enumerate(row):
                        if i < len(headers):
                            row_dict[headers[i]] = val
                    
                    name = str(row_dict.get('name', '')).strip()
                    sku = str(row_dict.get('sku', '')).strip()
                    
                    if not name or not sku:
                        errors.append(f'Row {idx}: Missing name or SKU')
                        continue
                    
                    existing = Product.query.filter_by(sku=sku).first()
                    if existing:
                        errors.append(f'Row {idx}: SKU "{sku}" already exists')
                        continue
                    
                    product = Product(
                        name=name,
                        sku=sku,
                        description=str(row_dict.get('description', '')).strip() if row_dict.get('description') else None,
                        category_id=int(row_dict.get('category_id')) if row_dict.get('category_id') else None,
                        unit_price=float(row_dict.get('unit_price', 0)) if row_dict.get('unit_price') else 0,
                        cost_price=float(row_dict.get('cost_price', 0)) if row_dict.get('cost_price') else 0,
                        quantity=float(row_dict.get('quantity', 0)) if row_dict.get('quantity') else 0,
                        reorder_level=float(row_dict.get('reorder_level', 0)) if row_dict.get('reorder_level') else 0,
                    )
                    
                    db.session.add(product)
                    added += 1
                except Exception as e:
                    errors.append(f'Row {idx}: {str(e)}')
            
            db.session.commit()
            
            if added > 0:
                flash(f'Successfully added {added} products!', 'success')
            if errors:
                flash(f'Errors: {"; ".join(errors[:10])}', 'warning')
            
            return redirect(url_for('inventory.products'))
            
        except Exception as e:
            flash(f'Error reading file: {str(e)}', 'error')
            return redirect(url_for('inventory.bulk_upload'))
    
    return render_template('inventory/bulk_upload.html')

@bp.route('/product/download-sample')
@login_required
def download_sample():
    try:
        from openpyxl import Workbook
        from io import BytesIO
        from flask import send_file
        
        wb = Workbook()
        ws = wb.active
        ws.title = 'Products'
        
        headers = ['name', 'sku', 'description', 'unit_price', 'cost_price', 'quantity', 'reorder_level', 'category_id']
        ws.append(headers)
        
        sample_data = [
            ['Product A', 'SKU-001', 'Description for Product A', 100.00, 50.00, 10, 5, ''],
            ['Product B', 'SKU-002', 'Description for Product B', 200.00, 100.00, 20, 10, ''],
            ['Product C', 'SKU-003', 'Description for Product C', 50.00, 25.00, 100, 20, '']
        ]
        
        for row in sample_data:
            ws.append(row)
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, download_name='sample_products.xlsx', as_attachment=True)
        
    except Exception as e:
        flash(f'Error creating sample: {str(e)}', 'error')
        return redirect(url_for('inventory.bulk_upload'))

@bp.route('/units/add', methods=['POST'])
@login_required
@permission_required('inventory', action='add')
def add_unit():
    name = request.form.get('name')
    if not name:
        return jsonify({'success': False, 'message': 'Unit name is required'})
    
    # Check if unit already exists (case-insensitive)
    existing = Unit.query.filter(func.lower(Unit.name) == func.lower(name)).first()
    if existing:
        return jsonify({'success': False, 'message': f'Unit "{name}" already exists'})
    
    try:
        unit = Unit(name=name)
        db.session.add(unit)
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Unit added successfully',
            'unit': {'id': unit.id, 'name': unit.name}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

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
        'category': product.category.name if product.category else product.category_name
    })

@bp.route('/product/<int:id>/full-history')
@login_required
def product_full_history(id):
    product = Product.query.get_or_404(id)
    
    # 1. Stock History (StockMovement)
    movements = StockMovement.query.filter_by(product_id=id).order_by(StockMovement.created_at.desc()).all()
    
    # 2. Sales History
    sales = SaleItem.query.filter_by(product_id=id).join(SaleItem.sale).order_by(Sale.date.desc()).all()
    
    # 3. Sales Return History
    sale_returns = SaleReturnItem.query.filter_by(product_id=id).join(SaleReturnItem.sale_return).order_by(SaleReturn.date.desc()).all()
    
    # 4. Purchase History
    purchases = sorted(PurchaseItem.query.filter_by(product_id=id).all(), key=lambda x: (x.bill.date if x.bill and x.bill.date else x.bill.created_at) if x.bill else datetime.min, reverse=True)
    
    # 5. Purchase Return History
    purchase_returns = PurchaseReturnItem.query.filter_by(product_id=id).join(PurchaseReturnItem.purchase_return).order_by(PurchaseReturn.date.desc()).all()
    
    # 6. Voucher Receiving (Tools)
    receivings = ToolReceivingItem.query.filter_by(product_id=id).join(ToolReceivingItem.receiving).order_by(ToolReceiving.date.desc()).all()
    
    # 7. Voucher Delivery (Tools)
    deliveries = ToolDeliveringItem.query.filter_by(product_id=id).join(ToolDeliveringItem.delivering).order_by(ToolDelivering.date.desc()).all()
    
    # 8. Activity Log (Edits/Deletes)
    activity_logs = ActivityLog.query.filter(
        ActivityLog.module == 'Inventory',
        ActivityLog.details.ilike(f'%SKU: {product.sku}%')
    ).order_by(ActivityLog.timestamp.desc()).all()

    # 9. Warehouse Specific History - Search by Name or SKU in action or details
    warehouse_history = ActivityLog.query.filter(
        ActivityLog.module == 'Warehouse',
        db.or_(
            ActivityLog.details.ilike(f'%{product.name}%'),
            ActivityLog.details.ilike(f'%{product.sku}%'),
            ActivityLog.action.ilike(f'%{product.name}%'),
            ActivityLog.action.ilike(f'%{product.sku}%')
        )
    ).order_by(ActivityLog.timestamp.desc()).all()

    # 10. Current Warehouse Distribution
    wh_distribution = []
    handled_wh_ids = set()
    
    # From bridge table
    for ws in product.warehouse_stocks:
        if ws.quantity != 0:
            wh_distribution.append({
                'warehouse_id': ws.warehouse_id,
                'warehouse_name': ws.warehouse.name,
                'quantity': ws.quantity
            })
            handled_wh_ids.add(ws.warehouse_id)
            
    # From legacy field
    if product.warehouse_id and product.warehouse_id not in handled_wh_ids and product.quantity != 0:
        wh_distribution.append({
            'warehouse_id': product.warehouse_id,
            'warehouse_name': product.warehouse.name,
            'quantity': product.quantity
        })



    # Calculate summary stats
    summary = {
        'total_sold': sum(item.quantity for item in sales),
        'total_purchased': sum(item.quantity for item in purchases),
        'total_returned_by_customer': sum(item.quantity for item in sale_returns),
        'total_returned_to_vendor': sum(item.quantity for item in purchase_returns),
        'total_received_tool': sum(item.quantity for item in receivings),
        'total_delivered_tool': sum(item.quantity for item in deliveries),
        'stock_value': product.stock_value
    }

    return render_template('inventory/product_full_history.html',
                         product=product,
                         movements=movements,
                         sales=sales,
                         sale_returns=sale_returns,
                         purchases=purchases,
                         purchase_returns=purchase_returns,
                         receivings=receivings,
                         deliveries=deliveries,
                         activity_logs=activity_logs,
                         warehouse_history=warehouse_history,
                         wh_distribution=wh_distribution,
                         summary=summary,
                         active_module='product')



@bp.route('/product/<int:id>/recalculate', methods=['POST'])
@login_required
@permission_required('inventory', action='edit')
def recalculate_stock(id):
    product = Product.query.get_or_404(id)
    
    # Recalculate total quantity from all sources
    # Start with 0 and add/subtract based on verified transactions
    history_qty = 0
    has_history = False
    
    # + Purchases (Only actually received stock)
    purchases_qty = db.session.query(func.sum(BillReceiveItem.quantity_received)).filter_by(product_id=id).scalar() or 0
    if purchases_qty > 0: has_history = True
    history_qty += purchases_qty
    
    # - Sales
    sales_qty = db.session.query(func.sum(SaleItem.quantity)).filter_by(product_id=id).scalar() or 0
    if sales_qty > 0: has_history = True
    history_qty -= sales_qty
    
    # + Sale Returns (Only if returned to inventory)
    sale_returns_qty = db.session.query(func.sum(SaleReturnItem.quantity))\
        .join(SaleReturn).filter(SaleReturnItem.product_id == id, SaleReturn.returned_to_inventory == True).scalar() or 0
    if sale_returns_qty > 0: has_history = True
    history_qty += sale_returns_qty
    
    # - Purchase Returns (Only if removed from inventory)
    purchase_returns_qty = db.session.query(func.sum(PurchaseReturnItem.quantity))\
        .join(PurchaseReturn).filter(PurchaseReturnItem.product_id == id, PurchaseReturn.returned_to_inventory == True).scalar() or 0
    if purchase_returns_qty > 0: has_history = True
    history_qty -= purchase_returns_qty
    
    # + Tool Receiving
    tool_receivings_qty = db.session.query(func.sum(ToolReceivingItem.quantity)).filter_by(product_id=id).scalar() or 0
    if tool_receivings_qty > 0: has_history = True
    history_qty += tool_receivings_qty
    
    # - Tool Delivering
    tool_deliveries_qty = db.session.query(func.sum(ToolDeliveringItem.quantity)).filter_by(product_id=id).scalar() or 0
    if tool_deliveries_qty > 0: has_history = True
    history_qty -= tool_deliveries_qty
    
    # +/- Manufacturing/Stock Adjustments (from StockMovement)
    mfg_in = db.session.query(func.sum(StockMovement.quantity)).filter_by(product_id=id, movement_type='in', reference_type='manufacturing_finish').scalar() or 0
    mfg_out = db.session.query(func.sum(StockMovement.quantity)).filter_by(product_id=id, movement_type='out', reference_type='manufacturing_usage').scalar() or 0
    if mfg_in > 0 or mfg_out > 0: has_history = True
    history_qty += mfg_in
    history_qty -= mfg_out

    # General adjustments
    adjust_in = db.session.query(func.sum(StockMovement.quantity)).filter_by(product_id=id, movement_type='in', reference_type='adjustment').scalar() or 0
    adjust_out = db.session.query(func.sum(StockMovement.quantity)).filter_by(product_id=id, movement_type='out', reference_type='adjustment').scalar() or 0
    if adjust_in > 0 or adjust_out > 0: has_history = True
    history_qty += adjust_in
    history_qty -= adjust_out

    old_qty = product.quantity
    
    # SAFETY CHECK: If no history exists at all but we have stock, DON'T set to zero.
    # This preserves opening balances and manual edits that lack movement logs.
    if not has_history and old_qty > 0:
        return jsonify({'success': True, 'old_qty': old_qty, 'new_qty': old_qty, 'message': 'No transaction history found to recalculate. Current stock preserved.'})

    # Otherwise, update with the history-based total
    product.quantity = history_qty
    total_qty = history_qty
    
    # Sync with primary warehouse if exists
    if product.warehouse_id:
        wh_stock = ProductWarehouseStock.query.filter_by(product_id=id, warehouse_id=product.warehouse_id).first()
        if wh_stock:
            wh_stock.quantity = total_qty
        else:
            wh_stock = ProductWarehouseStock(product_id=id, warehouse_id=product.warehouse_id, quantity=total_qty)
            db.session.add(wh_stock)

    try:
        db.session.commit()
        log_activity('Inventory', f'Recalculated Stock for {product.name}', f'SKU: {product.sku}, Old Qty: {old_qty}, New Qty: {total_qty}')
        return jsonify({'success': True, 'old_qty': old_qty, 'new_qty': total_qty, 'message': f'Stock recalculated successfully! New Quantity: {total_qty}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
