from flask import Blueprint, jsonify, url_for, request
from flask_login import login_required, current_user
from app.models import (
    db, Sale, PurchaseBill, Expense, Warehouse, Customer, Vendor,
    SaleReturn, PurchaseReturn, Product, Transaction, Payment,
    ManufacturingOrder, ManufacturingOrderItem, BOM
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
