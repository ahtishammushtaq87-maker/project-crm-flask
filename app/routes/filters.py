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


def apply_saved_filter_to_query(query, module, request_args):
    """
    Safely apply a saved filter to a SQLAlchemy query if filter_id is present.
    This is a ZERO-DAMAGE helper — it catches all errors and never raises.
    Use this in every list/report route to enable advanced filtering.
    """
    filter_id = request_args.get('filter_id', type=int)
    if not filter_id:
        return query
    sf = SavedFilter.query.get(filter_id)
    if not sf:
        flash(f'Saved filter #{filter_id} not found.', 'warning')
        return query
    if sf.module != module:
        # Module mismatch — don't break, just warn and ignore
        flash(f'Filter mismatch: expected {module}, got {sf.module}.', 'warning')
        return query
    try:
        query = apply_filters(query, module, sf.rules)
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
    else:
        # Create a temporary filter record so we can reference it by ID
        # We still save it but with a generated name so the redirect works.
        temp_name = f"__temp_{current_user.id}_{db.func.random()}"
        sf = SavedFilter(
            name=temp_name,
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
    final_url = f"{redirect_url}{separator}filter_id={sf.id}"

    return jsonify({
        'success': True,
        'filter_id': sf.id,
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

