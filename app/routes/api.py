from flask import Blueprint, jsonify, url_for, request, current_app
from flask_login import login_required, current_user
from app.models import (
    db, Sale, PurchaseBill, Expense, Warehouse, Customer, Vendor,
    SaleReturn, PurchaseReturn, Product, Transaction, Payment,
    ManufacturingOrder, ManufacturingOrderItem, BOM, BOMItem
)
from datetime import datetime

bp = Blueprint('api', __name__)

@bp.route('/entity-details/<entity_type>/<int:entity_id>')
@login_required
def get_entity_details(entity_type, entity_id):
    data = {
        'success': False,
        'title': 'Entity Details',
        'details': [],
        'history': [],
        'image': None,
        'actions': [],
        'split_history_layout': False
    }

    try:
        if entity_type == 'sale':
            entity = Sale.query.get_or_404(entity_id)
            data['title'] = f"Invoice: {entity.invoice_number}"
            data['details'] = [
                {'label': 'Date', 'value': entity.date.strftime('%Y-%m-%d')},
                {'label': 'Customer', 'value': entity.customer.name if entity.customer else 'Walk-in'},
                {'label': 'Total', 'value': f"PKR {entity.total:,.2f}"},
                {'label': 'Status', 'value': entity.status.capitalize(), 'class': f"badge bg-{'success' if entity.status == 'paid' else 'warning' if entity.status == 'partial' else 'danger'}"}
            ]
            
            # History
            data['history'].append({'date': entity.created_at, 'event': 'Invoice Created', 'type': 'create'})
            for p in entity.payments:
                data['history'].append({'date': p.date, 'event': f"Payment Received: PKR {p.amount:,.2f}", 'type': 'payment'})
            
            # Related returns
            returns = SaleReturn.query.filter_by(sale_id=entity.id).all()
            for r in returns:
                data['history'].append({'date': r.date, 'event': f"Return Created: {r.return_number}", 'type': 'return'})

            # Actions
            data['actions'] = []
            if entity.customer_id:
                data['actions'].append({'label': 'Ledger()', 'url': 'javascript:void(0)', 'btn_class': 'btn-outline-primary', 'onclick': f"showCustomerLedger({entity.customer_id}); bootstrap.Modal.getInstance(document.getElementById('entityHistoryModal')).hide();"})

            data['actions'].append({'label': 'View Full', 'url': url_for('sales.invoice_detail', id=entity.id), 'btn_class': 'btn-primary'})

            if entity.status != 'paid':
                # Always show Discount (regulated by backend logic)
                data['actions'].append({'label': 'Discount', 'url': 'javascript:void(0)', 'btn_class': 'btn-warning', 'onclick': f"bootstrap.Modal.getInstance(document.getElementById('entityHistoryModal')).hide(); window.location.href='{url_for('sales.invoice_detail', id=entity.id)}#discountModal'; setTimeout(() => {{ var m = new bootstrap.Modal(document.getElementById('discountModal')); m.show(); }}, 500);"})

                if entity.is_overdue:
                    # Plus Apply Advance for overdue
                    data['actions'].append({'label': 'Apply Advance', 'url': 'javascript:void(0)', 'btn_class': 'btn-danger', 'onclick': f"bootstrap.Modal.getInstance(document.getElementById('entityHistoryModal')).hide(); window.location.href='{url_for('sales.invoice_detail', id=entity.id)}#applyAdvanceModal'; setTimeout(() => {{ var m = new bootstrap.Modal(document.getElementById('applyAdvanceModal')); m.show(); }}, 500);"})

            data['actions'].extend([
                {'label': 'Edit', 'url': url_for('sales.edit_invoice', id=entity.id), 'btn_class': 'btn-info', 'permission': 'sales.edit'},
                {'label': 'Delete', 'url': url_for('sales.delete_invoice', id=entity.id), 'btn_class': 'btn-danger', 'permission': 'sales.delete', 'is_form': True}
            ])
            
            if entity.status != 'paid':
                data['actions'].append({'label': 'Return', 'url': url_for('returns.create_return', sale_id=entity.id), 'btn_class': 'btn-warning', 'permission': 'returns.add'})

        elif entity_type == 'purchase':
            entity = PurchaseBill.query.get_or_404(entity_id)
            data['title'] = f"Bill: {entity.bill_number}"
            data['details'] = [
                {'label': 'Date', 'value': entity.date.strftime('%Y-%m-%d')},
                {'label': 'Vendor', 'value': entity.vendor.name if entity.vendor else '-'},
                {'label': 'Total', 'value': f"PKR {entity.total:,.2f}"},
                {'label': 'Status', 'value': entity.status.capitalize(), 'class': 'badge bg-info'}
            ]
            if entity.bill_image_path:
                data['image'] = url_for('static', filename=entity.bill_image_path.replace('app/static/', '').replace('\\', '/'))
            
            # History
            data['history'].append({'date': entity.created_at, 'event': 'Bill Created', 'type': 'create'})
            # Payments history would go here if tracked similarly
            
            # Actions
            data['actions'] = [
                {'label': 'View Full', 'url': url_for('purchase.bill_detail', id=entity.id), 'btn_class': 'btn-primary'},
                {'label': 'Edit', 'url': url_for('purchase.edit_bill', id=entity.id), 'btn_class': 'btn-info', 'permission': 'purchases.edit'},
                {'label': 'Delete', 'url': url_for('purchase.delete_bill', id=entity.id), 'btn_class': 'btn-danger', 'permission': 'purchases.delete', 'is_form': True}
            ]

        elif entity_type == 'expense':
            entity = Expense.query.get_or_404(entity_id)
            data['title'] = f"Expense: {entity.expense_number}"
            data['details'] = [
                {'label': 'Date', 'value': entity.date.strftime('%Y-%m-%d')},
                {'label': 'Category', 'value': entity.expense_category.name if entity.expense_category else '-'},
                {'label': 'Amount', 'value': f"PKR {entity.amount:,.2f}"},
                {'label': 'Status', 'value': entity.status.capitalize(), 'class': 'badge bg-secondary'}
            ]
            if entity.bill_image_path:
                data['image'] = url_for('static', filename=entity.bill_image_path.replace('app/static/', '').replace('\\', '/'))

            data['history'].append({'date': entity.created_at, 'event': 'Expense Recorded', 'type': 'create'})
            
            data['actions'] = [
                {'label': 'Edit', 'url': url_for('accounting.edit_expense', id=entity.id), 'btn_class': 'btn-info', 'permission': 'expenses.edit'},
                {'label': 'Delete', 'url': url_for('accounting.delete_expense', id=entity.id), 'btn_class': 'btn-danger', 'permission': 'expenses.delete', 'is_form': True}
            ]

        elif entity_type == 'customer':
            entity = Customer.query.get_or_404(entity_id)
            data['title'] = f"Customer: {entity.name}"
            data['details'] = [
                {'label': 'Email', 'value': entity.email or '-'},
                {'label': 'Phone', 'value': entity.phone or '-'},
                {'label': 'Outstanding', 'value': f"PKR {entity.outstanding_balance:,.2f}", 'class': 'text-danger fw-bold'}
            ]
            
            # History: Last 5 Sales
            for s in entity.sales[:5]:
                data['history'].append({'date': s.date, 'event': f"Invoice {s.invoice_number}: PKR {s.total:,.2f}", 'type': 'sale'})

            data['actions'] = [
                {'label': 'Ledger()', 'url': 'javascript:void(0)', 'btn_class': 'btn-outline-primary', 'onclick': f"showCustomerLedger({entity.id}); bootstrap.Modal.getInstance(document.getElementById('entityHistoryModal')).hide();"},
                {'label': 'Edit', 'url': url_for('sales.edit_customer', id=entity.id), 'btn_class': 'btn-info', 'permission': 'customers.edit'},
                {'label': 'Full Profile', 'url': url_for('sales.customer_profile', id=entity.id), 'btn_class': 'btn-primary'}
            ]

        elif entity_type == 'vendor':
            entity = Vendor.query.get_or_404(entity_id)
            data['title'] = f"Vendor: {entity.name}"
            data['details'] = [
                {'label': 'Company', 'value': entity.company_name or '-'},
                {'label': 'Phone', 'value': entity.phone or '-'},
                {'label': 'Outstanding', 'value': f"PKR {entity.outstanding_balance:,.2f}", 'class': 'text-danger fw-bold'}
            ]
            if entity.image_path:
                data['image'] = url_for('static', filename=entity.image_path.replace('app/static/', '').replace('\\', '/'))
            
            # History: Last 5 Purchases
            for b in entity.bills[:5]:
                data['history'].append({'date': b.date, 'event': f"Bill {b.bill_number}: PKR {b.total:,.2f}", 'type': 'purchase'})

            data['actions'] = [
                {'label': 'Edit', 'url': url_for('purchase.edit_vendor', id=entity.id), 'btn_class': 'btn-info', 'permission': 'vendors.edit'},
                {'label': 'Full Profile', 'url': url_for('purchase.vendor_profile', id=entity.id), 'btn_class': 'btn-primary'}
            ]

        elif entity_type == 'warehouse':
            entity = Warehouse.query.get_or_404(entity_id)
            data['title'] = f"Warehouse: {entity.name}"
            data['details'] = [
                {'label': 'Code', 'value': entity.code},
                {'label': 'Address', 'value': entity.address or '-'},
                {'label': 'Manager', 'value': entity.manager or '-'}
            ]
            
            data['history'].append({'date': entity.created_at, 'event': 'Warehouse Registered', 'type': 'create'})

            data['actions'] = [
                {'label': 'View Detail', 'url': url_for('warehouse.warehouse_detail', id=entity.id), 'btn_class': 'btn-primary'},
                {'label': 'Edit', 'url': url_for('warehouse.edit_warehouse', id=entity.id), 'btn_class': 'btn-info', 'permission': 'warehouse.edit'}
            ]

        elif entity_type == 'inventory':
            entity = Product.query.get_or_404(entity_id)

            # History count filter: ?history_limit=5|10|20|all
            history_limit_raw = request.args.get('history_limit', '5')
            if history_limit_raw == 'all':
                history_limit = None
            else:
                try:
                    history_limit = int(history_limit_raw)
                except (ValueError, TypeError):
                    history_limit = 5

            data['title'] = f"History: {entity.sku} - {entity.name}"
            data['details'] = [
                {'label': 'SKU', 'value': entity.sku, 'class': 'fw-bold'},
                {'label': 'Category', 'value': entity.category.name if entity.category else '-'},
                {'label': 'Current Stock', 'value': f"{entity.quantity} {entity.unit}", 'class': f"badge bg-{'success' if entity.quantity > (entity.reorder_level or 0) else 'warning' if entity.quantity > 0 else 'danger'}"},
                {'label': 'Cost Price', 'value': f"PKR {entity.cost_price:,.2f}"},
                {'label': 'Selling Price', 'value': f"PKR {entity.unit_price:,.2f}"}
            ]
            if entity.image_path:
                data['image'] = url_for('static', filename=entity.image_path.replace('app/static/', '').replace('\\', '/'))

            # --- Sale history ---
            sale_items = entity.sale_items
            if history_limit:
                sale_items = sale_items[-history_limit:]
            for item in sale_items:
                customer_info = "Walk-in"
                if item.sale.customer:
                    profile_url = url_for('sales.customer_profile', id=item.sale.customer_id)
                    customer_info = f"<a href='{profile_url}' class='text-decoration-none'>{item.sale.customer.name}</a>"
                data['history'].append({
                    'date': item.sale.date,
                    'event': f"Sold {item.quantity} {entity.unit} to {customer_info} (Inv: {item.sale.invoice_number})",
                    'type': 'sale'
                })

            # --- Purchase history ---
            purchase_items = entity.purchase_items
            if history_limit:
                purchase_items = purchase_items[-history_limit:]
            for item in purchase_items:
                vendor_info = "Unknown"
                if item.bill.vendor:
                    profile_url = url_for('purchase.vendor_profile', id=item.bill.vendor_id)
                    vendor_info = f"<a href='{profile_url}' class='text-decoration-none'>{item.bill.vendor.name}</a>"
                data['history'].append({
                    'date': item.bill.date,
                    'event': f"Purchased {item.quantity} {entity.unit} from {vendor_info} (Bill: {item.bill.bill_number})",
                    'type': 'purchase'
                })

            # --- Manufacturing / Production history ---
            # Check if this product is a COMPONENT (used in MOItems)
            mo_items_as_component = ManufacturingOrderItem.query.filter_by(
                component_id=entity.id
            ).join(ManufacturingOrder).order_by(ManufacturingOrder.created_at.desc()).all()

            # Check if this product is a FINISHED GOOD (referenced via BOM)
            bom_as_finished = BOM.query.filter_by(product_id=entity.id).all()
            bom_ids_as_finished = [b.id for b in bom_as_finished]
            mo_as_finished_good = []
            if bom_ids_as_finished:
                mo_as_finished_good = ManufacturingOrder.query.filter(
                    ManufacturingOrder.bom_id.in_(bom_ids_as_finished)
                ).order_by(ManufacturingOrder.created_at.desc()).all()

            mfg_history = []
            # If it's a component
            for mo_item in mo_items_as_component:
                mo = mo_item.manufacturing_order
                finished_product = mo.bom.product if mo.bom else None
                finished_name = finished_product.name if finished_product else 'Unknown'
                mfg_history.append({
                    'date': mo.created_at,
                    'event': f"Used {mo_item.quantity_consumed or mo_item.quantity_required} {entity.unit} for <strong>{finished_name}</strong> (MO: {mo.order_number}, Status: {mo.status})",
                    'type': 'component_used'
                })
            # If it's a finished good
            for mo in mo_as_finished_good:
                mfg_history.append({
                    'date': mo.created_at,
                    'event': f"Produced {mo.produced_qty or 0} / {mo.quantity_to_produce} {entity.unit} (MO: {mo.order_number}, Status: {mo.status})",
                    'type': 'finished_good'
                })

            # Apply limit to mfg history
            mfg_history.sort(key=lambda x: x['date'], reverse=True)
            if history_limit:
                mfg_history = mfg_history[:history_limit]

            # Convert mfg dates
            for h in mfg_history:
                if isinstance(h['date'], datetime):
                    h['date'] = h['date'].strftime('%Y-%m-%d %H:%M')

            data['manufacturing_history'] = mfg_history
            data['history_limit'] = history_limit_raw
            data['entity_id'] = entity_id
            data['total_sale_count'] = len(entity.sale_items)
            data['total_purchase_count'] = len(entity.purchase_items)
            data['total_mfg_count'] = len(mo_items_as_component) + len(mo_as_finished_good)

            data['actions'] = [
                {'label': 'Where Used ?', 'url': 'javascript:void(0)', 'btn_class': 'btn-outline-indigo', 'onclick': f"showBOMAnalysis({entity.id})"},
                {'label': 'Complete History', 'url': url_for('inventory.product_full_history', id=entity.id), 'btn_class': 'btn-primary'},
                {'label': 'Price History', 'url': 'javascript:void(0)', 'btn_class': 'btn-success', 'onclick': f"showPriceHistory({entity.id}, '{entity.name.replace(chr(39), chr(92)+chr(39))}'); bootstrap.Modal.getInstance(document.getElementById('entityHistoryModal')).hide();"},
                {'label': 'Edit', 'url': url_for('inventory.edit_product', id=entity.id), 'btn_class': 'btn-info', 'permission': 'inventory.edit'},
                {'label': 'Delete', 'url': url_for('inventory.delete_product', id=entity.id), 'btn_class': 'btn-danger', 'permission': 'inventory.delete', 'is_form': True}
            ]

            data['split_history_layout'] = True
            data['has_manufacturing_history'] = True

        # Convert history dates to strings
        for h in data['history']:
            if isinstance(h['date'], datetime):
                h['date'] = h['date'].strftime('%Y-%m-%d %H:%M')
        
        # Sort history by date desc
        data['history'].sort(key=lambda x: x['date'], reverse=True)
        
        # Filter actions by permission
        filtered_actions = []
        for act in data['actions']:
            if 'permission' in act:
                module, action = act['permission'].split('.')
                if current_user.has_permission(module, action):
                    filtered_actions.append(act)
            else:
                filtered_actions.append(act)
        data['actions'] = filtered_actions
        
        data['success'] = True
    except Exception as e:
        data['error'] = str(e)

    return jsonify(data)

@bp.route('/product-bom-analysis/<int:product_id>')
@login_required
def get_product_bom_analysis(product_id):
    """Provides parent-child analysis for a product in terms of BOM and Manufacturing"""
    product = Product.query.get_or_404(product_id)
    
    data = {
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'quantity': product.quantity,
            'unit': product.unit or 'pcs'
        },
        'as_parent': [],
        'as_component': []
    }

    # 1. Analysis as a Finished Good (Parent)
    boms_as_parent = BOM.query.filter_by(product_id=product.id).all()
    for bom in boms_as_parent:
        # Get Manufacturing Orders for this BOM
        mos = ManufacturingOrder.query.filter_by(bom_id=bom.id).filter(ManufacturingOrder.status != 'Completed').all()
        # Sum quantities
        total_to_produce = sum(mo.quantity_to_produce for mo in mos)
        produced_so_far = sum(mo.produced_qty or 0 for mo in mos)
        
        bom_data = {
            'bom_id': bom.id,
            'bom_name': bom.name,
            'version': bom.version,
            'is_active': bom.is_active,
            'total_to_produce': total_to_produce,
            'produced_so_far': produced_so_far,
            'projected_qty': product.quantity + (total_to_produce - produced_so_far),
            'children': []
        }
        
        for item in bom.items:
            bom_data['children'].append({
                'id': item.component.id,
                'sku': item.component.sku,
                'name': item.component.name,
                'quantity_per_unit': item.quantity,
                'current_stock': item.component.quantity
            })
        
        data['as_parent'].append(bom_data)

    # 2. Analysis as a Component (Child)
    bom_items_as_child = BOMItem.query.filter_by(component_id=product.id).all()
    for item in bom_items_as_child:
        bom = item.bom
        # Total required for active MOs
        mo_items = ManufacturingOrderItem.query.filter_by(component_id=product.id).join(ManufacturingOrder).filter(
            ManufacturingOrder.bom_id == bom.id,
            ManufacturingOrder.status == 'In Progress'
        ).all()
        
        total_required_active = sum(mo_item.quantity_required - mo_item.quantity_consumed for mo_item in mo_items)
        
        data['as_component'].append({
            'parent_id': bom.product.id if bom.product else None,
            'parent_sku': bom.product.sku if bom.product else 'N/A',
            'parent_name': bom.product.name if bom.product else 'Unknown',
            'bom_version': bom.version,
            'quantity_used': item.quantity,
            'required_active_mo': total_required_active,
            'procurement_need': max(0, total_required_active - product.quantity)
        })

    return jsonify(data)


# ── Universal Approval API ────────────────────────────────────────────────────

@bp.route('/universal-approval', methods=['POST'])
@login_required
def universal_approval():
    """
    Unified approval endpoint. Accepts JSON body:
    {
        "module": "sale" | "payment" | "advance" | "expense" | "sale_return"
              | "purchase_return" | "purchase_order" | "purchase_bill",
        "item_id": <int>,
        "action": "approve" | "reject" | "cancel" | "draft",
        "reason": "<optional rejection reason>"
    }
    Returns JSON with success/failure.
    Admin-only.
    """
    from app.services.approval_service import ApprovalService

    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Only admin can perform approval actions.'}), 403

    data = request.get_json(silent=True) or {}
    module = data.get('module', '').strip().lower()
    item_id = data.get('item_id')
    action = data.get('action', '').strip().lower()
    reason = data.get('reason', '').strip()

    if not module or not item_id or not action:
        return jsonify({'success': False, 'message': 'Missing module, item_id, or action.'}), 400

    supported = ApprovalService.get_supported_modules()
    if module not in supported:
        return jsonify({'success': False, 'message': f"Unsupported module: {module}"}), 400

    config = ApprovalService.get_config(module)
    if action not in config.get('actions', []):
        return jsonify({'success': False, 'message': f"Action '{action}' not valid for {module}."}), 400

    try:
        if action == 'approve':
            entity, msg = ApprovalService.approve(module, item_id)
        elif action == 'reject':
            if not reason:
                return jsonify({'success': False, 'message': 'Rejection reason is required.'}), 400
            entity, msg = ApprovalService.reject(module, item_id, reason)
        elif action in ('cancel', 'draft'):
            entity, msg = ApprovalService.set_status(module, item_id, action)
        else:
            return jsonify({'success': False, 'message': f"Unknown action: {action}"}), 400

        return jsonify({
            'success': True,
            'message': msg,
            'status': ApprovalService.get_status(entity, module),
            'badge_class': ApprovalService.get_badge_class(ApprovalService.get_status(entity, module)),
        })
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Universal approval error: {e}")
        return jsonify({'success': False, 'message': 'Server error during approval.'}), 500


@bp.route('/universal-bulk-approval', methods=['POST'])
@login_required
def universal_bulk_approval():
    """
    Unified bulk approval endpoint. Accepts JSON body:
    {
        "module": "sale" | "payment" | ... ,
        "item_ids": [<int>, <int>, ...],
        "action": "approve" | "reject" | "cancel" | "draft",
        "reason": "<optional rejection reason>"
    }
    Returns JSON with success counts and messages.
    Admin-only.
    """
    from app.services.approval_service import ApprovalService

    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Only admin can perform approval actions.'}), 403

    data = request.get_json(silent=True) or {}
    module = data.get('module', '').strip().lower()
    item_ids = data.get('item_ids', [])
    action = data.get('action', '').strip().lower()
    reason = data.get('reason', '').strip()

    if not module or not item_ids or not action:
        return jsonify({'success': False, 'message': 'Missing module, item_ids, or action.'}), 400

    supported = ApprovalService.get_supported_modules()
    if module not in supported:
        return jsonify({'success': False, 'message': f"Unsupported module: {module}"}), 400

    config = ApprovalService.get_config(module)
    if action not in config.get('actions', []):
        return jsonify({'success': False, 'message': f"Action '{action}' not valid for {module}."}), 400

    if action == 'reject' and not reason:
        return jsonify({'success': False, 'message': 'Rejection reason is required.'}), 400

    success_count = 0
    errors = []

    for item_id in item_ids:
        try:
            if action == 'approve':
                ApprovalService.approve(module, item_id)
            elif action == 'reject':
                ApprovalService.reject(module, item_id, reason)
            elif action in ('cancel', 'draft'):
                ApprovalService.set_status(module, item_id, action)
            success_count += 1
        except Exception as e:
            errors.append(f"ID {item_id}: {str(e)}")

    if errors:
        msg = f"Processed {success_count} of {len(item_ids)} successfully. Errors: {'; '.join(errors)}"
        return jsonify({'success': success_count > 0, 'message': msg, 'success_count': success_count, 'errors': errors})

    return jsonify({
        'success': True,
        'message': f"Successfully performed '{action}' on {success_count} item(s).",
        'success_count': success_count
    })

