"""Routes for the Universal Query Builder / Saved Filters system."""
from flask import Blueprint, request, jsonify, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.filter_models import SavedFilter
from app.filter_engine import apply_filters, get_module_fields, validate_rules

bp = Blueprint('filters', __name__)


def _require_admin():
    """Helper to reject non-admins if needed later."""
    pass


import json
import base64

def apply_saved_filter_to_query(query, module, request_args):
    """
    Safely apply a saved filter to a SQLAlchemy query if filter_id is present.
    This is a ZERO-DAMAGE helper — it catches all errors and never raises.
    Use this in every list/report route to enable advanced filtering.
    """
    filter_id = request_args.get('filter_id', type=int)
    filter_rules_b64 = request_args.get('filter_rules', type=str)
    
    rules = None
    
    if filter_id:
        sf = SavedFilter.query.get(filter_id)
        if not sf:
            flash(f'Saved filter #{filter_id} not found.', 'warning')
            return query
        if sf.module != module:
            # Module mismatch — don't break, just warn and ignore
            flash(f'Filter mismatch: expected {module}, got {sf.module}.', 'warning')
            return query
        rules = sf.rules
    elif filter_rules_b64:
        try:
            json_str = base64.b64decode(filter_rules_b64).decode('utf-8')
            rules = json.loads(json_str)
        except Exception as e:
            flash(f'Error reading filter rules: {str(e)}', 'warning')
            return query

    if not rules:
        return query

    try:
        query = apply_filters(query, module, rules)
    except Exception as e:
        flash(f'Advanced filter error: {str(e)}', 'warning')
    return query


@bp.route('/')
@login_required
def list_filters():
    """GET /api/filters?module=expense  — list saved filters for a module."""
    module = request.args.get('module', '').strip().lower()
    if not module:
        return jsonify({'success': False, 'message': 'module parameter is required'}), 400
    items = SavedFilter.query.filter_by(module=module).order_by(SavedFilter.created_at.desc()).all()
    return jsonify({'success': True, 'filters': [f.to_dict() for f in items]})


@bp.route('/', methods=['POST'])
@login_required
def create_filter():
    """POST /api/filters — create a new saved filter."""
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    module = (data.get('module') or '').strip().lower()
    rules = data.get('rules')

    if not name:
        return jsonify({'success': False, 'message': 'name is required'}), 400
    if not module:
        return jsonify({'success': False, 'message': 'module is required'}), 400
    if not rules:
        return jsonify({'success': False, 'message': 'rules are required'}), 400

    ok, err = validate_rules(rules, module)
    if not ok:
        return jsonify({'success': False, 'message': err}), 400

    sf = SavedFilter(name=name, module=module, rules=rules)
    db.session.add(sf)
    db.session.commit()
    return jsonify({'success': True, 'filter': sf.to_dict()}), 201


@bp.route('/<int:id>', methods=['PUT'])
@login_required
def update_filter(id):
    """PUT /api/filters/<id> — update a saved filter."""
    sf = SavedFilter.query.get_or_404(id)
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    module = (data.get('module') or '').strip().lower()
    rules = data.get('rules')

    if name:
        sf.name = name
    if module:
        sf.module = module
    if rules is not None:
        ok, err = validate_rules(rules, sf.module)
        if not ok:
            return jsonify({'success': False, 'message': err}), 400
        sf.rules = rules

    db.session.commit()
    return jsonify({'success': True, 'filter': sf.to_dict()})


@bp.route('/<int:id>', methods=['DELETE'])
@login_required
def delete_filter(id):
    """DELETE /api/filters/<id> — delete a saved filter."""
    sf = SavedFilter.query.get_or_404(id)
    db.session.delete(sf)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Filter deleted'})


@bp.route('/fields')
@login_required
def list_fields():
    """GET /api/filters/fields?module=expense — return field metadata for the builder UI."""
    module = request.args.get('module', '').strip().lower()
    if not module:
        return jsonify({'success': False, 'message': 'module parameter is required'}), 400
    fields = get_module_fields(module)
    # Resolve options_route to actual URLs
    for f in fields:
        if f.get('options_route'):
            try:
                f['options_url'] = url_for(f['options_route'])
            except:
                f['options_url'] = None
    return jsonify({'success': True, 'module': module, 'fields': fields})


@bp.route('/apply', methods=['POST'])
@login_required
def apply_filter():
    """
    POST /api/filters/apply
    Body: {module, rules, save?: {name}, redirect_url?}
    Returns: {success, filter_id, redirect_url} or error.
    """
    data = request.get_json(silent=True) or {}
    module = (data.get('module') or '').strip().lower()
    rules = data.get('rules')
    save_info = data.get('save')  # optional {name: '...'}
    redirect_url = data.get('redirect_url')

    if not module:
        return jsonify({'success': False, 'message': 'module is required'}), 400
    if not rules:
        return jsonify({'success': False, 'message': 'rules are required'}), 400

    ok, err = validate_rules(rules, module)
    if not ok:
        return jsonify({'success': False, 'message': err}), 400

    # If user wants to persist this filter
    sf = None
    if save_info and save_info.get('name'):
        sf = SavedFilter(
            name=save_info['name'].strip(),
            module=module,
            rules=rules
        )
        db.session.add(sf)
        db.session.commit()

    # Build redirect URL
    if not redirect_url:
    # Default redirects per module
        redirects = {
            'expense': url_for('accounting.expenses'),
            'expense_report': url_for('reports.expense_report'),
            'sale': url_for('sales.invoices'),
            'sales_report': url_for('reports.sales_report'),
            'purchase': url_for('purchase.bills'),
            'purchase_report': url_for('reports.purchase_report'),
            'product': url_for('inventory.products'),
            'inventory_report': url_for('reports.inventory_report'),
            'manufacturing_order': url_for('manufacturing.orders'),
            'manufacturing_report': url_for('reports.manufacturing_report'),
            'bom': url_for('manufacturing.boms'),
            'bom_report': url_for('reports.bom_report'),
            'sale_return': url_for('returns.return_list'),
            'return_report': url_for('reports.return_report'),
            'purchase_return': url_for('purchase.purchase_return_list'),
            'purchase_order': url_for('purchase.purchase_orders'),
            'production_log': url_for('production.logs'),
            'salary_payment': url_for('reports.salary_report'),
            'salary_report': url_for('reports.salary_report'),
            'vendor': url_for('purchase.vendors'),
            'vendor_report': url_for('reports.vendor_report'),
            'customer': url_for('sales.customers'),
            'customer_report': url_for('reports.customer_report'),
            'staff': url_for('salary.staff_list'),
            'cogs_report': url_for('reports.cogs_report'),
            'profit_loss_report': url_for('reports.profit_loss_report'),
        }
        redirect_url = redirects.get(module, url_for('dashboard.index'))

    separator = '&' if '?' in redirect_url else '?'
    
    if sf:
        final_url = f"{redirect_url}{separator}filter_id={sf.id}"
        filter_id_val = sf.id
    else:
        import base64
        import json
        rules_str = json.dumps(rules)
        encoded_rules = base64.b64encode(rules_str.encode('utf-8')).decode('utf-8')
        final_url = f"{redirect_url}{separator}filter_rules={encoded_rules}"
        filter_id_val = None

    return jsonify({
        'success': True,
        'filter_id': filter_id_val,
        'redirect_url': final_url
    })


@bp.route('/<int:id>/test', methods=['POST'])
@login_required
def test_filter(id):
    """
    POST /api/filters/<id>/test
    Body: {module} (optional, inferred from saved filter)
    Returns count and first 5 matching IDs for quick preview.
    """
    sf = SavedFilter.query.get_or_404(id)
    module = sf.module
    rules = sf.rules

    # Lazy import models to keep module load light
    from app.models import Expense, Sale, PurchaseBill, Product
    model_map = {
        'expense': Expense,
        'sale': Sale,
        'purchase': PurchaseBill,
        'product': Product,
    }
    model_cls = model_map.get(module)
    if not model_cls:
        return jsonify({'success': False, 'message': f'Unsupported module: {module}'}), 400

    try:
        query = db.session.query(model_cls)
        query = apply_filters(query, module, rules)
        count = query.count()
        sample_ids = [r[0] for r in query.with_entities(model_cls.id).limit(5).all()]
        return jsonify({
            'success': True,
            'count': count,
            'sample_ids': sample_ids
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@bp.route('/options/salesmen')
@login_required
def get_salesmen():
    """Returns a list of active salesmen for lookup."""
    from app.models import Salesman
    items = Salesman.query.filter_by(is_active=True).order_by(Salesman.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.id, 'text': i.name} for i in items]
    })


@bp.route('/options/salesman_groups')
@login_required
def get_salesman_groups():
    """Returns a list of salesman groups for lookup."""
    from app.models import SalesmanGroup
    items = SalesmanGroup.query.order_by(SalesmanGroup.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items]
    })


@bp.route('/options/customers')
@login_required
def get_customers():
    """Returns a list of customers for lookup."""
    from app.models import Customer
    items = Customer.query.order_by(Customer.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items]
    })


@bp.route('/options/vendors')
@login_required
def get_vendors():
    """Returns a list of vendors for lookup."""
    from app.models import Vendor
    items = Vendor.query.order_by(Vendor.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items]
    })

@bp.route('/options/customer_groups')
@login_required
def get_customer_groups():
    """Returns a list of customer groups for lookup."""
    from app.models import CustomerGroup
    items = CustomerGroup.query.order_by(CustomerGroup.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items]
    })


@bp.route('/options/expense_categories')
@login_required
def get_expense_categories():
    """Returns a list of expense categories for lookup."""
    from app.models import ExpenseCategory
    items = ExpenseCategory.query.filter_by(is_active=True).order_by(ExpenseCategory.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items]
    })


@bp.route('/options/payment_methods')
@login_required
def get_payment_methods():
    """Returns a list of payment methods for lookup."""
    from app.models import PaymentMethod
    items = PaymentMethod.query.filter_by(is_active=True).order_by(PaymentMethod.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items]
    })


@bp.route('/options/product_categories')
@login_required
def get_product_categories():
    """Returns a list of product categories for lookup."""
    from app.models import ProductCategory
    items = ProductCategory.query.filter_by(is_active=True).order_by(ProductCategory.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items]
    })


@bp.route('/options/product_names')
@login_required
def get_product_names():
    """Returns a list of product names for lookup."""
    from app.models import Product
    items = Product.query.order_by(Product.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items]
    })


@bp.route('/options/product_skus')
@login_required
def get_product_skus():
    """Returns a list of product SKUs for lookup."""
    from app.models import Product
    items = Product.query.order_by(Product.sku).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.sku, 'text': i.sku} for i in items if i.sku]
    })


@bp.route('/options/invoice_numbers')
@login_required
def get_invoice_numbers():
    """Returns a list of invoice numbers for lookup."""
    from app.models import Sale
    items = Sale.query.order_by(Sale.invoice_number.desc()).limit(500).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.invoice_number, 'text': i.invoice_number} for i in items if i.invoice_number]
    })


@bp.route('/options/bill_numbers')
@login_required
def get_bill_numbers():
    """Returns a list of bill numbers for lookup."""
    from app.models import PurchaseBill
    items = PurchaseBill.query.order_by(PurchaseBill.bill_number.desc()).limit(500).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.bill_number, 'text': i.bill_number} for i in items if i.bill_number]
    })


@bp.route('/options/bom_names')
@login_required
def get_bom_names():
    """Returns a list of BOM names for lookup."""
    from app.models import BOM
    items = BOM.query.order_by(BOM.name).limit(500).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items if i.name]
    })


@bp.route('/options/mo_numbers')
@login_required
def get_mo_numbers():
    """Returns a list of Manufacturing Order numbers for lookup."""
    from app.models import ManufacturingOrder
    items = ManufacturingOrder.query.order_by(ManufacturingOrder.order_number.desc()).limit(500).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.order_number, 'text': i.order_number} for i in items if i.order_number]
    })


@bp.route('/options/warehouse_names')
@login_required
def get_warehouse_names():
    """Returns a list of warehouse names for lookup."""
    from app.models import Warehouse
    items = Warehouse.query.order_by(Warehouse.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items if i.name]
    })


@bp.route('/options/warehouse_codes')
@login_required
def get_warehouse_codes():
    """Returns a list of warehouse codes for lookup."""
    from app.models import Warehouse
    items = Warehouse.query.order_by(Warehouse.code).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.code, 'text': i.code} for i in items if i.code]
    })


@bp.route('/options/staff_names')
@login_required
def get_staff_names():
    """Returns a list of staff names for lookup."""
    from app.models import Staff
    items = Staff.query.order_by(Staff.name).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.name, 'text': i.name} for i in items if i.name]
    })


@bp.route('/options/return_numbers')
@login_required
def get_return_numbers():
    """Returns a list of sales return numbers for lookup."""
    from app.models import SaleReturn
    items = SaleReturn.query.order_by(SaleReturn.return_number.desc()).limit(500).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.return_number, 'text': i.return_number} for i in items if i.return_number]
    })


@bp.route('/options/purchase_return_numbers')
@login_required
def get_purchase_return_numbers():
    """Returns a list of purchase return numbers for lookup."""
    from app.models import PurchaseReturn
    items = PurchaseReturn.query.order_by(PurchaseReturn.return_number.desc()).limit(500).all()
    return jsonify({
        'success': True,
        'options': [{'id': i.return_number, 'text': i.return_number} for i in items if i.return_number]
    })
