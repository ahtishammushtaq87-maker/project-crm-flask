from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response
from flask_login import login_required, current_user
from app import db
from app.models import PurchaseBill, PurchaseItem, Product, Vendor, Company, Currency, VendorAdvance, PurchaseOrder, PurchaseOrderItem, CostPriceHistory, PurchaseReturn, PurchaseReturnItem, PurchaseSettings, PurchaseReturnSettings
from app.forms import PurchaseForm, VendorForm, PurchaseReturnSettingsForm
from datetime import datetime, timedelta, date
from app.pdf_utils import generate_professional_pdf
from app.services.bom_versioning import BOMVersioningService
import os
import io
import csv
import openpyxl
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER

bp = Blueprint('purchase', __name__)

@bp.route('/bills')
@login_required
def bills():
    status = request.args.get('status', 'all')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    search = request.args.get('search', '')
    
    query = PurchaseBill.query
    
    if status != 'all':
        query = query.filter(PurchaseBill.status == status)
    
    if from_date:
        try:
            query = query.filter(PurchaseBill.date >= datetime.strptime(from_date, '%Y-%m-%d'))
        except ValueError:
            pass
    
    if to_date:
        try:
            to_date_dt = datetime.strptime(to_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(PurchaseBill.date <= to_date_dt)
        except ValueError:
            pass

    if search:
        query = query.join(Vendor).filter(
            (PurchaseBill.bill_number.ilike(f'%{search}%')) |
            (Vendor.name.ilike(f'%{search}%'))
        )

    bills = query.order_by(PurchaseBill.date.desc()).all()
    
    # Summary totals for the view
    total_amount = sum(bill.total for bill in bills)
    total_paid = sum(bill.paid_amount for bill in bills)
    total_balance = sum(bill.balance_due for bill in bills)
    
    # Get company date format
    company = Company.query.first()
    date_format = company.date_format if company and company.date_format else '%Y-%m-%d'
    
    return render_template('purchase/bills.html', 
                         bills=bills, 
                         current_status=status,
                         from_date=from_date,
                         to_date=to_date,
                         search=search,
                         total_amount=total_amount,
                         total_paid=total_paid,
                         total_balance=total_balance,
                         date_format=date_format)

@bp.route('/bill/create', methods=['GET', 'POST'])
@login_required
def create_bill():
    form = PurchaseForm()
    vendors = Vendor.query.filter_by(is_active=True).all()
    products = Product.query.filter_by(is_active=True).all()
    currencies = Currency.query.filter_by(is_active=True).all()
    
    form.vendor_id.choices = [(v.id, v.name) for v in vendors]
    
    if form.validate_on_submit():
        vendor_id = form.vendor_id.data
        date = form.date.data

        # Get items from form
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')

        # Generate bill number using settings
        settings = PurchaseSettings.query.first()
        if not settings:
            settings = PurchaseSettings(bill_prefix='PB-', bill_suffix='', next_bill_number=1,
                                        po_prefix='PO-', po_suffix='', next_po_number=1)
            db.session.add(settings)
        bill_number = f"{settings.bill_prefix}{settings.next_bill_number}{settings.bill_suffix}"
        settings.next_bill_number += 1
        
        bill = PurchaseBill(
            bill_number=bill_number,
            vendor_id=vendor_id,
            date=date,
            due_date=date + timedelta(days=30),
            tax_rate=float(request.form.get('tax_rate', 0)),
            discount=float(request.form.get('discount', 0)),
            shipping_charge=float(request.form.get('shipping_charge', 0)),
            currency_id=request.form.get('currency_id'),
            exchange_rate=float(request.form.get('exchange_rate', 1)),
            notes=request.form.get('notes'),
            created_by=current_user.id
        )
        
        db.session.add(bill)

        # First, collect all items and calculate totals
        items_data = []
        total_items_cost = 0
        
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                prod_id = int(product_ids[i])
                qty = float(quantities[i])
                price = float(prices[i])
                item_total = qty * price
                
                items_data.append({
                    'product_id': prod_id,
                    'quantity': qty,
                    'unit_price': price,
                    'total': item_total
                })
                total_items_cost += item_total
        
        # Get shipping and tax
        shipping_charge = float(request.form.get('shipping_charge', 0))
        tax_rate = float(request.form.get('tax_rate', 0))
        
        # Calculate tax on items + shipping
        taxable_amount = total_items_cost + shipping_charge
        tax_amount = (taxable_amount * tax_rate) / 100 if tax_rate > 0 else 0
        
        # Total additional cost to allocate (shipping + tax)
        total_additional_cost = shipping_charge + tax_amount
        
        # Add items with allocated shipping and tax
        for item_data in items_data:
            prod_id = item_data['product_id']
            qty = item_data['quantity']
            price = item_data['unit_price']
            item_total = item_data['total']
            
            # Allocate shipping and tax proportionally based on item cost
            if total_items_cost > 0:
                allocation_ratio = item_total / total_items_cost
                allocated_additional = total_additional_cost * allocation_ratio
            else:
                allocated_additional = 0
            
            # New cost per unit including allocated shipping and tax
            new_unit_cost = price + (allocated_additional / qty) if qty > 0 else price
            
            item = PurchaseItem(
                product_id=prod_id,
                quantity=qty,
                unit_price=price,
                total=item_total
            )
            bill.items.append(item)
            
            # Update inventory (increase stock)
            product = Product.query.get(prod_id)
            if product:
                product.update_quantity(qty)
                
                # Track cost price change with allocated shipping and tax
                old_price = product.cost_price
                
                # Create cost price history entry with the new cost including shipping/tax
                cost_history = CostPriceHistory(
                    product_id=prod_id,
                    purchase_bill_id=bill.id,
                    old_price=old_price if old_price > 0 else None,
                    new_price=new_unit_cost,
                    quantity_at_old_price=product.quantity - qty,  # Qty at old price = total qty - new qty
                    used_quantity=0,
                    reason=f"Purchase bill with shipping Rs {shipping_charge} and tax {tax_rate}% - Base: Rs {price}, New: Rs {new_unit_cost:.2f}",
                    is_active=True,
                    created_by=current_user.id
                )
                db.session.add(cost_history)
                
                # Update product's cost price to new price (including shipping and tax allocation)
                product.cost_price = new_unit_cost
        
        bill.calculate_totals()
        
        # Update paid amount from "Advance Paid" field in template
        advance = float(request.form.get('advance', 0))
        if advance > 0:
            vendor = Vendor.query.get(vendor_id)
            pending_advances = VendorAdvance.query.filter_by(
                vendor_id=vendor.id
            ).order_by(VendorAdvance.date).all()
            
            remaining_to_apply = advance
            for adv in pending_advances:
                if remaining_to_apply <= 0:
                    break
                # Apply as much as possible from this advance
                can_apply = min(adv.remaining_balance, remaining_to_apply)
                if can_apply > 0:
                    adv.applied_amount += can_apply
                    bill.paid_amount += can_apply
                    if adv.applied_amount >= adv.amount:
                        adv.is_adjusted = True
                        adv.adjusted_bill_id = bill.id
                    else:
                        adv.adjusted_bill_id = bill.id
                    remaining_to_apply -= can_apply
            
            # If there's still remaining advance payment, add it as cash payment
            if remaining_to_apply > 0:
                bill.paid_amount += remaining_to_apply
        else:
            bill.paid_amount = 0
            
        if bill.paid_amount >= bill.total:
            bill.status = 'paid'
        elif bill.paid_amount > 0:
            bill.status = 'partial'
        else:
            bill.status = 'unpaid'

        db.session.commit()
        
        # Trigger BOM versioning for any products that had cost changes
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                prod_id = int(product_ids[i])
                try:
                    # Safe user_id resolution
                    user_id = None
                    try:
                        if current_user and current_user.is_authenticated:
                            user_id = current_user.id
                    except (AttributeError, TypeError):
                        pass
                    if user_id is None:
                        from app.models import User
                        admin_user = User.query.filter_by(username='admin').first()
                        user_id = admin_user.id if admin_user else 1
                    
                    BOMVersioningService.check_and_update_bom_for_cost_changes(
                        product_id=prod_id,
                        created_by_id=user_id
                    )
                except Exception as e:
                    print(f"Error updating BOM versions for product {prod_id}: {e}")
        
        flash('Purchase bill created successfully!', 'success')
        return redirect(url_for('purchase.bill_detail', id=bill.id))
    
    return render_template('purchase/create_bill.html', form=form, products=products, vendors=vendors, currencies=currencies)

@bp.route('/bill/<int:id>')
@login_required
def bill_detail(id):
    bill = PurchaseBill.query.get_or_404(id)
    company = Company.query.first()
    date_format = company.date_format if company and company.date_format else '%Y-%m-%d'
    return render_template('purchase/bill_detail.html', bill=bill, date_format=date_format)

@bp.route('/bill/<int:id>/update-shipping', methods=['POST'])
@login_required
def update_shipping(id):
    """Update shipping charge and recalculate product costs"""
    bill = PurchaseBill.query.get_or_404(id)
    
    try:
        new_shipping = float(request.form.get('shipping_charge', 0))
        old_shipping = bill.shipping_charge
        
        if new_shipping < 0:
            flash('Shipping charge cannot be negative', 'danger')
            return redirect(request.referrer or url_for('purchase.bill_detail', id=id))
        
        # Update shipping
        bill.shipping_charge = new_shipping
        bill.calculate_totals()
        
        # Recalculate product costs to include new shipping
        total_items_cost = sum(item.total for item in bill.items)
        if total_items_cost > 0:
            for item in bill.items:
                product = Product.query.get(item.product_id)
                if product:
                    # Calculate new cost including proportional shipping (based on item cost, not qty)
                    # Also include tax in allocation
                    taxable_amount = total_items_cost + new_shipping
                    tax_amount = (taxable_amount * bill.tax_rate) / 100 if bill.tax_rate > 0 else 0
                    total_additional = new_shipping + tax_amount
                    
                    # Allocate based on item cost ratio
                    allocation_ratio = item.total / total_items_cost if total_items_cost > 0 else 0
                    allocated_additional = total_additional * allocation_ratio
                    
                    new_cost_price = item.unit_price + (allocated_additional / item.quantity)
                    
                    if product.cost_price != new_cost_price:
                        old_price = product.cost_price
                        
                        # Create cost price history entry
                        cost_history = CostPriceHistory(
                            product_id=item.product_id,
                            purchase_bill_id=bill.id,
                            old_price=old_price if old_price > 0 else None,
                            new_price=new_cost_price,
                            quantity_at_old_price=product.quantity - item.quantity,
                            used_quantity=0,
                            reason=f"Shipping update - Old Shipping: Rs {old_shipping}, New Shipping: Rs {new_shipping}",
                            is_active=True,
                            created_by=current_user.id
                        )
                        db.session.add(cost_history)
                        
                        # Update product cost price
                        product.cost_price = new_cost_price
                        
                        # Trigger BOM versioning
                        try:
                            user_id = None
                            try:
                                if current_user and current_user.is_authenticated:
                                    user_id = current_user.id
                            except (AttributeError, TypeError):
                                pass
                            if user_id is None:
                                from app.models import User
                                admin_user = User.query.filter_by(username='admin').first()
                                user_id = admin_user.id if admin_user else 1
                            
                            BOMVersioningService.check_and_update_bom_for_cost_changes(
                                product_id=item.product_id,
                                created_by_id=user_id
                            )
                        except Exception as e:
                            print(f"Error updating BOM for shipping change: {e}")
        
        db.session.commit()
        flash(f'Shipping charge updated to Rs {new_shipping:,.2f}. Product costs recalculated!', 'success')
        
    except ValueError:
        flash('Invalid shipping amount', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating shipping: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('purchase.bill_detail', id=id))

@bp.route('/bill/<int:id>/update-tax', methods=['POST'])
@login_required
def update_tax(id):
    """Update tax rate and recalculate product costs"""
    bill = PurchaseBill.query.get_or_404(id)
    
    try:
        new_tax_rate = float(request.form.get('tax_rate', 0))
        old_tax_rate = bill.tax_rate
        
        if new_tax_rate < 0 or new_tax_rate > 100:
            flash('Tax rate must be between 0 and 100', 'danger')
            return redirect(request.referrer or url_for('purchase.bill_detail', id=id))
        
        # Update tax rate
        bill.tax_rate = new_tax_rate
        bill.calculate_totals()
        
        # Recalculate product costs to include new tax
        total_items_cost = sum(item.total for item in bill.items)
        if total_items_cost > 0:
            for item in bill.items:
                product = Product.query.get(item.product_id)
                if product:
                    # Calculate new cost including proportional tax (based on item cost, not qty)
                    # Also include shipping in calculation
                    taxable_amount = total_items_cost + bill.shipping_charge
                    new_tax_total = (taxable_amount * new_tax_rate) / 100 if new_tax_rate > 0 else 0
                    total_additional = bill.shipping_charge + new_tax_total
                    
                    # Allocate based on item cost ratio
                    allocation_ratio = item.total / total_items_cost if total_items_cost > 0 else 0
                    allocated_additional = total_additional * allocation_ratio
                    
                    new_cost_price = item.unit_price + (allocated_additional / item.quantity)
                    
                    if product.cost_price != new_cost_price:
                        old_price = product.cost_price
                        
                        # Create cost price history entry
                        cost_history = CostPriceHistory(
                            product_id=item.product_id,
                            purchase_bill_id=bill.id,
                            old_price=old_price if old_price > 0 else None,
                            new_price=new_cost_price,
                            quantity_at_old_price=product.quantity - item.quantity,
                            used_quantity=0,
                            reason=f"Tax rate update - Old Tax Rate: {old_tax_rate}%, New Tax Rate: {new_tax_rate}%",
                            is_active=True,
                            created_by=current_user.id
                        )
                        db.session.add(cost_history)
                        
                        # Update product cost price
                        product.cost_price = new_cost_price
                        
                        # Trigger BOM versioning
                        try:
                            user_id = None
                            try:
                                if current_user and current_user.is_authenticated:
                                    user_id = current_user.id
                            except (AttributeError, TypeError):
                                pass
                            if user_id is None:
                                from app.models import User
                                admin_user = User.query.filter_by(username='admin').first()
                                user_id = admin_user.id if admin_user else 1
                            
                            BOMVersioningService.check_and_update_bom_for_cost_changes(
                                product_id=item.product_id,
                                created_by_id=user_id
                            )
                        except Exception as e:
                            print(f"Error updating BOM for tax change: {e}")
        
        db.session.commit()
        flash(f'Tax rate updated to {new_tax_rate}%. Product costs recalculated!', 'success')
        
    except ValueError:
        flash('Invalid tax rate', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating tax: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('purchase.bill_detail', id=id))

@bp.route('/bill/<int:id>/pdf')
@login_required
def bill_pdf(id):
    bill = PurchaseBill.query.get_or_404(id)
    company = Company.query.first()
    from app.models import PurchaseSettings
    settings = PurchaseSettings.query.first()
    
    try:
        buffer = generate_professional_pdf('purchase', bill, company, settings)
        
        response = make_response(buffer)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="bill_{bill.bill_number}.pdf"'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('purchase.bill_detail', id=id))

@bp.route('/bill/<int:id>/pdf/view')
@login_required
def bill_pdf_view(id):
    """View PDF inline for sharing"""
    bill = PurchaseBill.query.get_or_404(id)
    company = Company.query.first()
    from app.models import PurchaseSettings
    settings = PurchaseSettings.query.first()
    
    try:
        buffer = generate_professional_pdf('purchase', bill, company, settings)
        return send_file(buffer, mimetype='application/pdf')
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('purchase.bill_detail', id=id))

@bp.route('/bill/<int:id>/pdf/share')
@login_required
def bill_pdf_share(id):
    """Generate PDF, save to public folder, and return shareable link"""
    from flask import current_app
    import os
    import secrets
    
    bill = PurchaseBill.query.get_or_404(id)
    company = Company.query.first()
    from app.models import PurchaseSettings
    settings = PurchaseSettings.query.first()
    
    try:
        buffer = generate_professional_pdf('purchase', bill, company, settings)
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        
        public_dir = os.path.join(current_app.root_path, 'static', 'shared_pdfs')
        os.makedirs(public_dir, exist_ok=True)
        
        token = secrets.token_urlsafe(8)
        filename = f"bill_{bill.bill_number}_{token}.pdf"
        filepath = os.path.join(public_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(pdf_data)
        
        share_url = url_for('static', filename=f'shared_pdfs/{filename}')
        return {'share_url': share_url}
    except Exception as e:
        return {'error': str(e)}, 500


@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def purchase_settings_page():
    from app.forms import PurchaseSettingsForm
    from app.models import PurchaseSettings
    settings = PurchaseSettings.query.first()
    
    form = PurchaseSettingsForm(obj=settings)
    
    if request.method == 'POST':
        if not settings:
            settings = PurchaseSettings()
            db.session.add(settings)
        
        settings.default_notes = form.default_notes.data
        settings.default_terms = form.default_terms.data
        settings.bill_prefix = form.bill_prefix.data or ''
        settings.bill_suffix = form.bill_suffix.data or ''
        settings.next_bill_number = form.next_bill_number.data or 1
        settings.po_prefix = form.po_prefix.data or ''
        settings.po_suffix = form.po_suffix.data or ''
        settings.next_po_number = form.next_po_number.data or 1
        
        db.session.commit()
        flash('Purchase settings saved!', 'success')
        return redirect(url_for('purchase.purchase_settings_page'))
    
    return render_template('purchase/purchase_settings.html', settings=settings, form=form)


@bp.route('/bill/<int:id>/pay', methods=['POST'])
@login_required
def pay_bill(id):
    bill = PurchaseBill.query.get_or_404(id)
    payment_method = request.form.get('payment_method', 'cash')
    
    vendor = bill.vendor
    total_payment = 0
    
    try:
        if payment_method == 'cash':
            # Simple cash payment
            amount = float(request.form.get('amount', 0))
            if amount > 0:
                total_payment = amount
                bill.paid_amount += amount
                
        elif payment_method == 'advance':
            # Payment using selected advance
            advance_id = request.form.get('selected_advance_id')
            if advance_id:
                advance = VendorAdvance.query.get(int(advance_id))
                if advance and advance.vendor_id == vendor.id:
                    can_apply = min(advance.remaining_balance, bill.balance_due)
                    if can_apply > 0:
                        advance.applied_amount += can_apply
                        bill.paid_amount += can_apply
                        if advance.applied_amount >= advance.amount:
                            advance.is_adjusted = True
                            advance.adjusted_bill_id = bill.id
                        else:
                            advance.adjusted_bill_id = bill.id
                        total_payment = can_apply
                        
        elif payment_method == 'mixed':
            # Mixed payment - advances + cash
            # Get selected advances
            advance_ids = request.form.getlist('value')
            cash_amount = float(request.form.get('cash_amount', 0))
            
            remaining_to_apply = bill.balance_due
            
            # Apply advances first
            for advance_id in advance_ids:
                if remaining_to_apply <= 0:
                    break
                advance = VendorAdvance.query.get(int(advance_id))
                if advance and advance.vendor_id == vendor.id:
                    can_apply = min(advance.remaining_balance, remaining_to_apply)
                    if can_apply > 0:
                        advance.applied_amount += can_apply
                        bill.paid_amount += can_apply
                        if advance.applied_amount >= advance.amount:
                            advance.is_adjusted = True
                            advance.adjusted_bill_id = bill.id
                        else:
                            advance.adjusted_bill_id = bill.id
                        total_payment += can_apply
                        remaining_to_apply -= can_apply
            
            # Apply cash payment
            if cash_amount > 0 and remaining_to_apply > 0:
                cash_to_apply = min(cash_amount, remaining_to_apply)
                bill.paid_amount += cash_to_apply
                total_payment += cash_to_apply
        
        # Update bill status
        if bill.paid_amount >= bill.total:
            bill.status = 'paid'
        elif bill.paid_amount > 0:
            bill.status = 'partial'
        else:
            bill.status = 'unpaid'
        
        db.session.commit()
        
        if total_payment > 0:
            method_text = f'({payment_method.capitalize()})'
            flash(f'Payment of Rs {total_payment:,.2f} recorded successfully! {method_text}', 'success')
        else:
            flash('No payment was processed.', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing payment: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('purchase.bill_detail', id=bill.id))

@bp.route('/bill/<int:id>/discount', methods=['POST'])
@login_required
def apply_discount(id):
    bill = PurchaseBill.query.get_or_404(id)
    discount_amount = float(request.form.get('discount_amount', 0))
    
    if discount_amount > 0:
        bill.discount += discount_amount
        bill.calculate_totals()
        bill.update_status()
        
        db.session.commit()
        flash(f'Discount of Rs {discount_amount} applied successfully!', 'success')
    
    return redirect(request.referrer or url_for('purchase.bill_detail', id=bill.id))

@bp.route('/bill/<int:id>/delete', methods=['POST'])
@login_required
def delete_bill(id):
    bill = PurchaseBill.query.get_or_404(id)
    # Revert inventory (decrease stock added by this purchase)
    for item in bill.items:
        product = Product.query.get(item.product_id)
        if product:
            product.update_quantity(-item.quantity)

    db.session.delete(bill)
    db.session.commit()
    flash('Purchase bill deleted successfully.', 'success')
    return redirect(url_for('purchase.bills'))

@bp.route('/bills/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_bills():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'message': 'No bills selected'}), 400
    
    deleted_count = 0
    errors = []
    
    for bill_id in ids:
        bill = PurchaseBill.query.get(bill_id)
        if not bill:
            continue
            
        try:
            # Revert inventory
            for item in bill.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(-item.quantity)
            
            db.session.delete(bill)
            deleted_count += 1
        except Exception as e:
            db.session.rollback()
            errors.append(f'Error deleting Bill {bill.bill_number}: {str(e)}')
            
    if deleted_count > 0:
        db.session.commit()
        
    message = f'Successfully deleted {deleted_count} bills.'
    if errors:
        return jsonify({'success': False, 'message': message, 'errors': errors}), 500
    return jsonify({'success': True, 'message': message})

@bp.route('/vendors')
@login_required
def vendors():
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    vendor_id = request.args.get('vendor_id', type=int)
    
    query = Vendor.query
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    if vendor_id:
        query = query.filter_by(id=vendor_id)
    elif search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Vendor.name.ilike(search_filter)) |
            (Vendor.email.ilike(search_filter)) |
            (Vendor.phone.ilike(search_filter))
        )
    
    vendors = query.order_by(Vendor.name.asc()).all()
    # List of all vendors for the searchable dropdown
    all_vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    
    return render_template('purchase/vendors.html', 
                         vendors=vendors,
                         all_vendors=all_vendors, 
                         current_status=status, 
                         search_query=search,
                         selected_vendor_id=vendor_id)

@bp.route('/vendor/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload_vendor():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('purchase.bulk_upload_vendor'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('purchase.bulk_upload_vendor'))
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('Please upload an Excel file (.xlsx or .xls)', 'error')
            return redirect(url_for('purchase.bulk_upload_vendor'))
        
        try:
            from openpyxl import load_workbook
            from io import BytesIO
            wb = load_workbook(filename=BytesIO(file.read()), read_only=True)
            ws = wb.active
            rows = list(ws.values)
            if not rows:
                flash('File is empty', 'error')
                return redirect(url_for('purchase.bulk_upload_vendor'))
            headers = [str(h) if h else '' for h in rows[0]]
            df_data = []
            for row in rows[1:]:
                df_data.append({headers[i]: row[i] for i in range(len(headers))})
            import pandas as pd
            df = pd.DataFrame(df_data)
            
            required_columns = ['name']
            missing = [col for col in required_columns if col not in df.columns]
            if missing:
                flash(f'Missing required columns: {", ".join(missing)}', 'error')
                return redirect(url_for('purchase.bulk_upload_vendor'))
            
            added = 0
            errors = []
            
            for idx, row in df.iterrows():
                try:
                    name = str(row.get('name', '')).strip()
                    
                    if not name:
                        errors.append(f'Row {idx + 2}: Missing name')
                        continue
                    
                    vendor = Vendor(
                        name=name,
                        email=str(row.get('email', '')).strip() if pd.notna(row.get('email')) else None,
                        phone=str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else None,
                        address=str(row.get('address', '')).strip() if pd.notna(row.get('address')) else None,
                        shipping_address=str(row.get('shipping_address', '')).strip() if pd.notna(row.get('shipping_address')) else None,
                        gst_number=str(row.get('gst_number', '')).strip() if pd.notna(row.get('gst_number')) else None,
                        pan_number=str(row.get('pan_number', '')).strip() if pd.notna(row.get('pan_number')) else None,
                        contact_person=str(row.get('contact_person', '')).strip() if pd.notna(row.get('contact_person')) else None,
                    )
                    
                    db.session.add(vendor)
                    added += 1
                except Exception as e:
                    errors.append(f'Row {idx + 2}: {str(e)}')
            
            db.session.commit()
            
            if added > 0:
                flash(f'Successfully added {added} vendors!', 'success')
            if errors:
                flash(f'Errors: {"; ".join(errors[:10])}', 'warning')
            
            return redirect(url_for('purchase.vendors'))
            
        except Exception as e:
            flash(f'Error reading file: {str(e)}', 'error')
            return redirect(url_for('purchase.bulk_upload_vendor'))
    
    return render_template('purchase/bulk_upload_vendor.html')

@bp.route('/vendor/download-sample')
@login_required
def download_vendor_sample():
    try:
        from openpyxl import Workbook
        from io import BytesIO
        from flask import send_file
        
        wb = Workbook()
        ws = wb.active
        ws.title = 'Vendors'
        
        headers = ['name', 'email', 'phone', 'address', 'shipping_address', 'gst_number', 'pan_number', 'contact_person']
        ws.append(headers)
        
        sample_data = [
            ['Vendor A', 'vendorA@example.com', '1234567890', '123 Factory St, City', '123 Factory St, City', 'GST123456789', 'ABCDE1234F', 'John Doe'],
            ['Vendor B', 'vendorB@example.com', '2345678901', '456 Warehouse Ave, Town', '456 Warehouse Ave, Town', 'GST987654321', 'FGHI5678K', 'Jane Smith'],
            ['Vendor C', 'vendorC@example.com', '3456789012', '789 Supply Rd, Village', '789 Supply Rd, Village', '', '', '']
        ]
        
        for row in sample_data:
            ws.append(row)
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, download_name='sample_vendors.xlsx', as_attachment=True)
        
    except Exception as e:
        flash(f'Error creating sample: {str(e)}', 'error')
        return redirect(url_for('purchase.vendors'))

@bp.route('/vendor/<int:id>')
@login_required
def vendor_profile(id):
    vendor = Vendor.query.get_or_404(id)
    # Sort bills newest first
    bills = sorted(vendor.bills, key=lambda b: b.date, reverse=True)
    # Sort advances newest first
    advances = sorted(vendor.advances, key=lambda a: a.date, reverse=True)
    return render_template('purchase/vendor_profile.html',
                           vendor=vendor,
                           bills=bills,
                           advances=advances)

@bp.route('/vendor/add', methods=['GET', 'POST'])
@login_required
def add_vendor():
    form = VendorForm()
    if form.validate_on_submit():
        vendor = Vendor(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            gst_number=form.gst_number.data,
            payment_method=form.payment_method.data
        )
        db.session.add(vendor)
        db.session.commit()
        flash('Vendor added successfully!', 'success')
        return redirect(url_for('purchase.vendors'))
    
    return render_template('purchase/add_vendor.html', form=form)


@bp.route('/vendor/<int:id>/advance', methods=['POST'])
@login_required
def vendor_give_advance(id):
    """Record a quick advance payment given to a vendor against material."""
    vendor = Vendor.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    description = request.form.get('description', '').strip()
    advance_date_str = request.form.get('advance_date', '')
    
    if amount <= 0:
        flash('Advance amount must be greater than zero.', 'danger')
        return redirect(url_for('purchase.vendor_profile', id=id))
    
    try:
        advance_date = datetime.strptime(advance_date_str, '%Y-%m-%d').date() if advance_date_str else date.today()
    except ValueError:
        advance_date = date.today()
    
    advance = VendorAdvance(
        vendor_id=vendor.id,
        amount=amount,
        date=advance_date,
        description=description or 'Advance against material',
        created_by=current_user.id
    )
    db.session.add(advance)
    db.session.commit()
    flash(f'Advance of Rs {amount:,.2f} recorded for {vendor.name}.', 'success')
    return redirect(url_for('purchase.vendor_profile', id=id))


@bp.route('/vendor/<int:id>/advance/<int:adv_id>/adjust', methods=['POST'])
@login_required
def vendor_adjust_advance(id, adv_id):
    """Apply a vendor advance against a specific bill."""
    advance = VendorAdvance.query.get_or_404(adv_id)
    bill_id = request.form.get('bill_id')
    
    # Check if advance still has remaining balance
    if advance.remaining_balance <= 0:
        flash('This advance has no remaining balance to apply.', 'warning')
        return redirect(url_for('purchase.vendor_profile', id=id))
    
    if bill_id:
        bill = PurchaseBill.query.get(int(bill_id))
        if bill and bill.vendor_id == id:
            # Calculate how much of the advance can be applied to this bill
            bill_remaining = bill.total - bill.paid_amount
            apply_amount = min(advance.remaining_balance, bill_remaining)
            
            if apply_amount > 0:
                # Deduct the applied amount from the advance and bill
                advance.applied_amount += apply_amount
                bill.paid_amount += apply_amount
                bill.update_status()
                
                # Mark as fully adjusted only if the entire advance amount is applied
                if advance.applied_amount >= advance.amount:
                    advance.is_adjusted = True
                    advance.adjusted_bill_id = bill.id
                    db.session.commit()
                    flash(f'Advance of Rs {apply_amount:,.2f} fully applied to bill {bill.bill_number}.', 'success')
                else:
                    db.session.commit()
                    flash(f'Advance of Rs {apply_amount:,.2f} applied to bill {bill.bill_number}. Remaining Rs {advance.remaining_balance:,.2f} still available as advance.', 'success')
            return redirect(url_for('purchase.vendor_profile', id=id))
    return redirect(url_for('purchase.vendor_profile', id=id))


@bp.route('/vendor/<int:id>/advance/<int:adv_id>/delete', methods=['POST'])
@login_required
def vendor_delete_advance(id, adv_id):
    """Delete a vendor advance (reverses applied amount from bill if any was applied)."""
    advance = VendorAdvance.query.get_or_404(adv_id)
    if advance.vendor_id != id:
        flash('Invalid advance.', 'danger')
        return redirect(url_for('purchase.vendor_profile', id=id))
    
    # Reverse the applied amount from the adjusted bill
    if advance.applied_amount > 0 and advance.adjusted_bill_id:
        bill = PurchaseBill.query.get(advance.adjusted_bill_id)
        if bill:
            bill.paid_amount = max(0, bill.paid_amount - advance.applied_amount)
            bill.update_status()
    
    db.session.delete(advance)
    db.session.commit()
    flash('Advance deleted and any applied amount has been reversed.', 'success')
    return redirect(url_for('purchase.vendor_profile', id=id))

@bp.route('/vendor/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_vendor(id):
    vendor = Vendor.query.get_or_404(id)
    form = VendorForm(obj=vendor)
    
    if form.validate_on_submit():
        vendor.name = form.name.data
        vendor.email = form.email.data
        vendor.phone = form.phone.data
        vendor.address = form.address.data
        vendor.gst_number = form.gst_number.data
        vendor.payment_method = form.payment_method.data
        db.session.commit()
        flash('Vendor updated successfully!', 'success')
        return redirect(url_for('purchase.vendors'))
    
    return render_template('purchase/edit_vendor.html', form=form, vendor=vendor)

@bp.route('/vendor/<int:id>/delete', methods=['POST'])
@login_required
def delete_vendor(id):
    vendor = Vendor.query.get_or_404(id)
    
    # Check if vendor has associated records (Purchases or Sales)
    if vendor.bills or vendor.sales or vendor.expenses:
        flash('Cannot delete vendor as they have associated transaction records.', 'danger')
        return redirect(url_for('purchase.vendors'))

    db.session.delete(vendor)
    db.session.commit()
    flash('Vendor deleted successfully!', 'success')
    return redirect(url_for('purchase.vendors'))

@bp.route('/vendors/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_vendors():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'message': 'No vendors selected'}), 400
    
    deleted_count = 0
    skipped_count = 0
    errors = []
    
    for vendor_id in ids:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            continue
            
        # Check associations
        if vendor.bills or vendor.sales or vendor.expenses:
            skipped_count += 1
            continue
            
        try:
            db.session.delete(vendor)
            deleted_count += 1
        except Exception as e:
            db.session.rollback()
            errors.append(f'Error deleting Vendor {vendor.name}: {str(e)}')
            
    if deleted_count > 0:
        db.session.commit()
        
    message = f'Successfully deleted {deleted_count} vendors.'
    if skipped_count > 0:
        message += f' Skipped {skipped_count} vendors with associated records.'
    
    if errors:
        return jsonify({'success': False, 'message': message, 'errors': errors}), 500
    return jsonify({'success': True, 'message': message})


# ---------------------------------------------------------------------------
# AJAX: Vendor advance info (used by create_bill and create_po forms)
# ---------------------------------------------------------------------------
@bp.route('/api/vendor/<int:vendor_id>/advances')
@login_required
def vendor_advance_info(vendor_id):
    """Return JSON with pending (unadjusted) advance balance for a vendor."""
    vendor = Vendor.query.get_or_404(vendor_id)
    pending = [a for a in vendor.advances if a.remaining_balance > 0]
    return jsonify({
        'vendor_id': vendor_id,
        'vendor_name': vendor.name,
        'total_advances': vendor.total_advances_given,
        'total_adjusted': vendor.total_advances_adjusted,
        'pending_balance': vendor.remaining_advance_balance,
        'advances': [
            {
                'id': a.id,
                'amount': a.amount,
                'applied_amount': a.applied_amount,
                'remaining': a.remaining_balance,
                'date': a.date.strftime('%d-%m-%Y'),
                'description': a.description or ''
            }
            for a in pending
        ]
    })


# ---------------------------------------------------------------------------
# AJAX: confirmed POs for a vendor (used by create_bill form)
# ---------------------------------------------------------------------------
@bp.route('/api/vendor/<int:vendor_id>/purchase-orders')
@login_required
def vendor_pos(vendor_id):
    """Return confirmed POs for a vendor (for the create-bill dropdown)."""
    pos = PurchaseOrder.query.filter_by(
        vendor_id=vendor_id, status='Confirmed'
    ).order_by(PurchaseOrder.date.desc()).all()
    return jsonify([
        {
            'id': po.id,
            'po_number': po.po_number,
            'date': po.date.strftime('%d-%m-%Y'),
            'total': po.total,
            'items': [
                {
                    'product_id': item.product_id,
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'total': item.total
                }
                for item in po.items
            ],
            'shipping_charge': po.shipping_charge,
            'notes': po.notes or ''
        }
        for po in pos
    ])


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------
@bp.route('/orders')
@login_required
def purchase_orders():
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')

    query = PurchaseOrder.query
    if status != 'all':
        query = query.filter_by(status=status)
    if search:
        query = query.join(Vendor).filter(
            PurchaseOrder.po_number.ilike(f'%{search}%') |
            Vendor.name.ilike(f'%{search}%')
        )
    orders = query.order_by(PurchaseOrder.date.desc()).all()
    return render_template('purchase/purchase_orders.html',
                           orders=orders, current_status=status, search=search)


def _parse_delivery_time(dt_str):
    """Parse datetime-local input string."""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        try:
            return datetime.strptime(dt_str, '%Y-%m-%d')
        except ValueError:
            return None


@bp.route('/order/create', methods=['GET', 'POST'])
@login_required
def create_po():
    vendors = Vendor.query.filter_by(is_active=True).all()
    products = Product.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        vendor_id = int(request.form.get('vendor_id'))
        expected_date_str = request.form.get('expected_date', '')
        expected_date = datetime.strptime(expected_date_str, '%Y-%m-%d') if expected_date_str else None

        product_ids = request.form.getlist('product_id[]')
        quantities  = request.form.getlist('quantity[]')
        prices      = request.form.getlist('price[]')

        # Auto-generate PO number using settings
        settings = PurchaseSettings.query.first()
        if not settings:
            settings = PurchaseSettings(bill_prefix='PB-', bill_suffix='', next_bill_number=1,
                                        po_prefix='PO-', po_suffix='', next_po_number=1)
            db.session.add(settings)
        po_number = f"{settings.po_prefix}{settings.next_po_number}{settings.po_suffix}"
        settings.next_po_number += 1

        po = PurchaseOrder(
            po_number=po_number,
            vendor_id=vendor_id,
            date=datetime.utcnow(),
            expected_date=expected_date,
            delivery_start=_parse_delivery_time(request.form.get('delivery_start')),
            delivery_end=_parse_delivery_time(request.form.get('delivery_end')),
            advance_amount=float(request.form.get('advance_amount', 0)),
            shipping_charge=float(request.form.get('shipping_charge', 0)),
            tax_rate=float(request.form.get('tax_rate', 0)),
            discount=float(request.form.get('discount', 0)),
            notes=request.form.get('notes', ''),
            status='Draft',
            created_by=current_user.id
        )
        db.session.add(po)

        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                qty   = float(quantities[i])
                price = float(prices[i])
                item  = PurchaseOrderItem(
                    product_id=int(product_ids[i]),
                    quantity=qty,
                    unit_price=price,
                    total=qty * price
                )
                po.items.append(item)

        po.calculate_totals()
        
        # If advance amount is paid, also record it as vendor advance
        advance_amount = float(request.form.get('advance_amount', 0))
        if advance_amount > 0:
            vendor_advance = VendorAdvance(
                vendor_id=vendor_id,
                amount=advance_amount,
                date=datetime.utcnow().date(),
                description=f'Advance for PO {po_number}',
                created_by=current_user.id
            )
            db.session.add(vendor_advance)
        
        db.session.commit()
        flash(f'Purchase Order {po.po_number} created!', 'success')
        return redirect(url_for('purchase.po_detail', id=po.id))

    return render_template('purchase/create_po.html', vendors=vendors, products=products)


@bp.route('/order/<int:id>')
@login_required
def po_detail(id):
    po = PurchaseOrder.query.get_or_404(id)
    start_ts = int(po.delivery_start.timestamp()) if po.delivery_start else None
    end_ts = int(po.delivery_end.timestamp()) if po.delivery_end else None
    return render_template('purchase/po_detail.html', po=po, start_ts=start_ts, end_ts=end_ts)


@bp.route('/order/<int:id>/pdf')
@login_required
def po_pdf(id):
    """Generate PDF for a Purchase Order."""
    po = PurchaseOrder.query.get_or_404(id)
    from app.models import Company
    company = Company.query.first()
    
    buffer = generate_professional_pdf('purchase_order', po, company, None)
    response = make_response(buffer)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename="{po.po_number}.pdf"'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@bp.route('/order/<int:id>/pdf/view')
@login_required
def po_pdf_view(id):
    """View PDF inline for sharing"""
    po = PurchaseOrder.query.get_or_404(id)
    from app.models import Company
    company = Company.query.first()
    
    buffer = generate_professional_pdf('purchase_order', po, company, None)
    return send_file(buffer, mimetype='application/pdf')

@bp.route('/order/<int:id>/pdf/share')
@login_required
def po_pdf_share(id):
    """Generate PDF, save to public folder, and return shareable link"""
    from flask import current_app
    import os
    import secrets
    
    po = PurchaseOrder.query.get_or_404(id)
    from app.models import Company
    company = Company.query.first()
    
    try:
        buffer = generate_professional_pdf('purchase_order', po, company, None)
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        
        public_dir = os.path.join(current_app.root_path, 'static', 'shared_pdfs')
        os.makedirs(public_dir, exist_ok=True)
        
        token = secrets.token_urlsafe(8)
        filename = f"po_{po.po_number}_{token}.pdf"
        filepath = os.path.join(public_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(pdf_data)
        
        share_url = url_for('static', filename=f'shared_pdfs/{filename}')
        return {'share_url': share_url}
    except Exception as e:
        return {'error': str(e)}, 500


@bp.route('/order/<int:id>/confirm', methods=['POST'])
@login_required
def confirm_po(id):
    po = PurchaseOrder.query.get_or_404(id)
    if po.status == 'Draft':
        po.status = 'Confirmed'
        db.session.commit()
        flash(f'Purchase Order {po.po_number} confirmed. You can now create a bill from it.', 'success')
    else:
        flash('Only Draft orders can be confirmed.', 'warning')
    return redirect(url_for('purchase.po_detail', id=id))


@bp.route('/order/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_po(id):
    po = PurchaseOrder.query.get_or_404(id)
    if po.status in ('Draft', 'Confirmed'):
        po.status = 'Cancelled'
        db.session.commit()
        flash(f'Purchase Order {po.po_number} cancelled.', 'warning')
    else:
        flash('Cannot cancel a Converted or already Cancelled order.', 'danger')
    return redirect(url_for('purchase.po_detail', id=id))


@bp.route('/order/<int:id>/convert', methods=['POST'])
@login_required
def convert_po_to_bill(id):
    """Convert a confirmed PO into a Purchase Bill, pre-filling all items."""
    po = PurchaseOrder.query.get_or_404(id)
    if po.status != 'Confirmed':
        flash('Only Confirmed orders can be converted to a bill.', 'danger')
        return redirect(url_for('purchase.po_detail', id=id))

    last_bill = PurchaseBill.query.order_by(PurchaseBill.id.desc()).first()
    # Generate bill number using settings
    settings = PurchaseSettings.query.first()
    if not settings:
        settings = PurchaseSettings(bill_prefix='PB-', bill_suffix='', next_bill_number=1,
                                    po_prefix='PO-', po_suffix='', next_po_number=1)
        db.session.add(settings)
    bill_number = f"{settings.bill_prefix}{settings.next_bill_number}{settings.bill_suffix}"
    settings.next_bill_number += 1

    bill = PurchaseBill(
        bill_number=bill_number,
        vendor_id=po.vendor_id,
        po_id=po.id,
        date=datetime.utcnow(),
        due_date=datetime.utcnow() + timedelta(days=30),
        tax_rate=po.tax_rate,
        discount=po.discount,
        shipping_charge=po.shipping_charge,
        notes=po.notes,
        created_by=current_user.id
    )
    db.session.add(bill)

    for poi in po.items:
        item = PurchaseItem(
            product_id=poi.product_id,
            quantity=poi.quantity,
            unit_price=poi.unit_price,
            total=poi.total
        )
        bill.items.append(item)
        # Update inventory
        product = Product.query.get(poi.product_id)
        if product:
            product.update_quantity(poi.quantity)

    bill.calculate_totals()
    po.status = 'Converted'
    db.session.commit()

    flash(f'Bill {bill.bill_number} created from PO {po.po_number}!', 'success')
    return redirect(url_for('purchase.bill_detail', id=bill.id))


@bp.route('/order/<int:id>/delete', methods=['POST'])
@login_required
def delete_po(id):
    po = PurchaseOrder.query.get_or_404(id)
    db.session.delete(po)
    db.session.commit()
    flash('Purchase Order deleted.', 'success')
    return redirect(url_for('purchase.purchase_orders'))

@bp.route('/purchase-orders/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_purchase_orders():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'message': 'No orders selected'}), 400
    
    deleted_count = 0
    errors = []
    
    for po_id in ids:
        po = PurchaseOrder.query.get(po_id)
        if not po:
            continue
            
        try:
            db.session.delete(po)
            deleted_count += 1
        except Exception as e:
            db.session.rollback()
            errors.append(f'Error deleting Order {po.po_number}: {str(e)}')
            
    if deleted_count > 0:
        db.session.commit()
        
    message = f'Successfully deleted {deleted_count} orders.'
    if errors:
        return jsonify({'success': False, 'message': message, 'errors': errors}), 500
    return jsonify({'success': True, 'message': message})


# ---------------------------------------------------------------------------
# API: Get cost price history for a product
# ---------------------------------------------------------------------------
@bp.route('/api/product/<int:product_id>/cost-history')
@login_required
def product_cost_history(product_id):
    """Return JSON with cost price history for a product"""
    product = Product.query.get_or_404(product_id)
    history = CostPriceHistory.query.filter_by(product_id=product_id).order_by(CostPriceHistory.change_date.desc()).all()
    
    return jsonify({
        'product_id': product_id,
        'product_name': product.name,
        'current_cost_price': product.cost_price,
        'total_quantity': product.quantity,
        'history': [
            {
                'id': h.id,
                'old_price': h.old_price or 0,
                'new_price': h.new_price,
                'quantity_at_old_price': h.quantity_at_old_price,
                'remaining_at_old_price': h.remaining_at_old_price,
                'used_quantity': h.used_quantity,
                'change_date': h.change_date.strftime('%d-%m-%Y %H:%M'),
                'reason': h.reason,
                'is_active': h.is_active,
                'purchase_bill_id': h.purchase_bill_id
            }
            for h in history
        ]
    })


# ---------------------------------------------------------------------------
# Purchase Returns
# ---------------------------------------------------------------------------
@bp.route('/returns/')
@login_required
def purchase_return_list():
    """List all purchase returns"""
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    status = request.args.get('status', 'all')

    query = PurchaseReturn.query

    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
            query = query.filter(PurchaseReturn.date >= from_date_obj)
        except ValueError:
            pass

    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')
            to_date_obj = to_date_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(PurchaseReturn.date <= to_date_obj)
        except ValueError:
            pass

    if status != 'all':
        query = query.filter(PurchaseReturn.status == status)

    returns = query.order_by(PurchaseReturn.date.desc()).all()

    total_returns = sum(r.total for r in returns)
    total_count = len(returns)

    return render_template('purchase/returns.html',
                        returns=returns,
                        from_date=from_date,
                        to_date=to_date,
                        current_status=status,
                        total_returns=total_returns,
                        total_count=total_count)


@bp.route('/return/create', methods=['GET', 'POST'])
@login_required
def create_purchase_return():
    """Create a new purchase return"""
    if request.method == 'GET':
        bill_id = request.args.get('bill_id')
        if bill_id:
            bill = PurchaseBill.query.get_or_404(int(bill_id))
            return render_template('purchase/create_return.html',
                               bill=bill,
                               products=Product.query.filter_by(is_active=True).all(),
                               now=datetime.now())

        bills = PurchaseBill.query.order_by(PurchaseBill.date.desc()).all()
        return render_template('purchase/create_return.html',
                           bills=bills,
                           bill=None,
                           products=Product.query.filter_by(is_active=True).all(),
                           now=datetime.now())

    # POST - process return
    bill_id = request.form.get('bill_id')
    bill = PurchaseBill.query.get_or_404(int(bill_id))

    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    prices = request.form.getlist('price[]')

    subtotal = 0
    return_items = []

    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
            product = Product.query.get(int(product_ids[i]))
            quantity = float(quantities[i])
            price = float(prices[i])
            total = quantity * price
            subtotal += total

            return_items.append({
                'product_id': product.id,
                'quantity': quantity,
                'unit_price': price,
                'total': total
            })

    if not return_items:
        flash('Please add at least one item to return.', 'warning')
        return redirect(url_for('purchase.create_purchase_return', bill_id=bill_id))

    tax_rate = float(request.form.get('tax_rate', 0))
    tax = subtotal * (tax_rate / 100)
    discount = float(request.form.get('discount', 0))
    total = subtotal + tax - discount

    # Generate return number using settings
    settings = PurchaseReturnSettings.query.first()
    if not settings:
        settings = PurchaseReturnSettings(return_prefix='PRet-', return_suffix='', next_number=1)
        db.session.add(settings)

    # Sync next_number with actual highest return number in DB
    highest_return = PurchaseReturn.query.order_by(PurchaseReturn.id.desc()).first()
    if highest_return and highest_return.return_number:
        try:
            prefix_len = len(settings.return_prefix or '')
            suffix_len = len(settings.return_suffix or '')
            num_str = highest_return.return_number[prefix_len:]
            if suffix_len > 0:
                num_str = num_str[:-suffix_len]
            max_num = int(num_str)
            next_return_num = max(settings.next_number, max_num + 1)
        except (ValueError, IndexError):
            next_return_num = settings.next_number
    else:
        next_return_num = settings.next_number

    # Get unique return number
    prefix = settings.return_prefix or ''
    suffix = settings.return_suffix or ''
    while True:
        return_number = f"{prefix}{next_return_num}{suffix}"
        existing = PurchaseReturn.query.filter_by(return_number=return_number).first()
        if not existing:
            break
        next_return_num += 1

    purchase_return = PurchaseReturn(
        return_number=return_number,
        bill_id=bill.id,
        vendor_id=bill.vendor_id,
        date=datetime.strptime(request.form.get('date'), '%Y-%m-%d') if request.form.get('date') else datetime.now(),
        subtotal=subtotal,
        tax_rate=tax_rate,
        tax=tax,
        discount=discount,
        total=total,
        reason=request.form.get('reason', ''),
        status='pending',
        returned_to_inventory=False,
        refund_status='none',
        created_by=current_user.id
    )

    db.session.add(purchase_return)
    db.session.flush()

    # Create return items
    for item in return_items:
        return_item = PurchaseReturnItem(
            return_id=purchase_return.id,
            product_id=item['product_id'],
            quantity=item['quantity'],
            unit_price=item['unit_price'],
            total=item['total']
        )
        db.session.add(return_item)

        # Subtract from inventory
        product = Product.query.get(item['product_id'])
        if product:
            product.quantity -= item['quantity']
            if product.quantity < 0:
                product.quantity = 0

    # Update bill totals - reduce bill total by return amount
    bill.subtotal -= subtotal
    bill.tax -= tax
    bill.total -= total
    if bill.total < 0:
        bill.total = 0

    # Adjust paid amount if needed
    if bill.paid_amount > 0:
        if bill.total < bill.paid_amount:
            bill.paid_amount = bill.total

    # Update bill status based on return
    original_total = bill.total + total  # Restore original to compare
    if original_total > 0:
        if bill.total == 0 or total >= original_total:
            bill.status = 'return'
        elif total > 0 and bill.total < original_total:
            bill.status = 'partial_return'
        else:
            bill.status = bill.status  # Keep existing status

    # Update return settings next number
    settings.next_number = next_return_num + 1

    db.session.commit()
    flash(f'Purchase return {return_number} created successfully!', 'success')
    return redirect(url_for('purchase.purchase_return_detail', id=purchase_return.id))


@bp.route('/return/<int:id>')
@login_required
def purchase_return_detail(id):
    """View purchase return detail"""
    purchase_return = PurchaseReturn.query.get_or_404(id)
    return render_template('purchase/return_detail.html', return_obj=purchase_return)


@bp.route('/return/<int:id>/mark_returned', methods=['POST'])
@login_required
def mark_purchase_returned(id):
    """Mark return as returned to inventory"""
    purchase_return = PurchaseReturn.query.get_or_404(id)
    
    if not purchase_return.returned_to_inventory:
        purchase_return.returned_to_inventory = True
        purchase_return.status = 'completed'
        db.session.commit()
        flash('Items marked as returned to inventory.', 'success')
    else:
        flash('Items already returned to inventory.', 'info')
    
    return redirect(url_for('purchase.purchase_return_detail', id=id))


@bp.route('/return/<int:id>/refund', methods=['POST'])
@login_required
def process_purchase_refund(id):
    """Process refund to vendor"""
    purchase_return = PurchaseReturn.query.get_or_404(id)
    
    refund_amount = float(request.form.get('refund_amount', 0))
    
    if refund_amount <= 0:
        flash('Please enter a valid refund amount.', 'warning')
        return redirect(url_for('purchase.purchase_return_detail', id=id))
    
    if refund_amount > purchase_return.total:
        refund_amount = purchase_return.total
    
    purchase_return.refund_amount = refund_amount
    purchase_return.refund_status = 'paid'
    purchase_return.status = 'completed'
    
    # Create a vendor advance record for the refund (negative = refund paid to vendor)
    if purchase_return.vendor:
        vendor_advance = VendorAdvance(
            vendor_id=purchase_return.vendor.id,
            amount=-refund_amount,  # Negative amount to represent refund
            date=datetime.now(),
            description=f'Refund for Return: {purchase_return.return_number}',
            created_by=current_user.id
        )
        db.session.add(vendor_advance)
    
    db.session.commit()
    flash(f'Refund of Rs{refund_amount:,.2f} processed to vendor.', 'success')
    return redirect(url_for('purchase.purchase_return_detail', id=id))


@bp.route('/returns/vendor/<int:vendor_id>')
@login_required
def vendor_purchase_returns(vendor_id):
    """View all purchase returns for a vendor"""
    vendor = Vendor.query.get_or_404(vendor_id)
    returns = PurchaseReturn.query.filter_by(vendor_id=vendor_id).order_by(PurchaseReturn.date.desc()).all()
    
    return render_template('purchase/vendor_returns.html',
                        vendor=vendor,
                        returns=returns)


@bp.route('/return/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_purchase_return(id):
    """Edit a purchase return"""
    purchase_return = PurchaseReturn.query.get_or_404(id)
    bill = purchase_return.bill
    
    if request.method == 'POST':
        purchase_return.reason = request.form.get('reason', '')
        purchase_return.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d') if request.form.get('date') else purchase_return.date
        
        # Update quantities and recalculate totals
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        
        # Delete existing items
        for item in purchase_return.items:
            # Restore product quantity
            if item.product:
                item.product.quantity += item.quantity
            db.session.delete(item)
        
        # Create new items
        subtotal = 0
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                product = Product.query.get(int(product_ids[i]))
                quantity = float(quantities[i])
                price = float(prices[i])
                total = quantity * price
                subtotal += total
                
                return_item = PurchaseReturnItem(
                    return_id=purchase_return.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=price,
                    total=total
                )
                db.session.add(return_item)
                
                # Subtract from inventory
                if product:
                    product.quantity -= quantity
                    if product.quantity < 0:
                        product.quantity = 0
        
        # Recalculate totals
        tax_rate = purchase_return.tax_rate
        tax = subtotal * (tax_rate / 100)
        discount = purchase_return.discount
        total = subtotal + tax - discount
        
        purchase_return.subtotal = subtotal
        purchase_return.tax = tax
        purchase_return.total = total
        
        db.session.commit()
        flash(f'Return {purchase_return.return_number} updated successfully!', 'success')
        return redirect(url_for('purchase.purchase_return_detail', id=id))
    
    return render_template('purchase/edit_return.html',
                          return_obj=purchase_return,
                          products=Product.query.filter_by(is_active=True).all())


@bp.route('/return/<int:id>/delete', methods=['POST'])
@login_required
def delete_purchase_return(id):
    """Delete a purchase return"""
    purchase_return = PurchaseReturn.query.get_or_404(id)
    bill = purchase_return.bill
    
    # Restore product quantities
    for item in purchase_return.items:
        if item.product:
            item.product.quantity += item.quantity
    
    # Reverse vendor refund if was paid
    if purchase_return.refund_status == 'paid' and purchase_return.vendor:
        # Create a positive vendor advance to reverse the refund
        vendor_advance = VendorAdvance(
            vendor_id=purchase_return.vendor.id,
            amount=purchase_return.refund_amount,
            date=datetime.now(),
            description=f'Reversal for Return: {purchase_return.return_number}',
            created_by=current_user.id
        )
        db.session.add(vendor_advance)
    
    # Restore bill totals and recalculate status
    if bill:
        bill.subtotal += purchase_return.subtotal
        bill.tax += purchase_return.tax
        bill.total += purchase_return.total
        
        # Recalculate bill status based on paid amount vs total
        if bill.paid_amount >= bill.total and bill.total > 0:
            bill.status = 'paid'
        elif bill.paid_amount > 0 and bill.paid_amount < bill.total:
            bill.status = 'partial'
        else:
            bill.status = 'unpaid'
    
    return_number = purchase_return.return_number
    db.session.delete(purchase_return)
    db.session.commit()
    
    flash(f'Return {return_number} deleted successfully!', 'success')
    return redirect(url_for('purchase.purchase_return_list'))
@bp.route('/return/settings', methods=['GET', 'POST'])
@login_required
def purchase_return_settings():
    settings = PurchaseReturnSettings.query.first()
    form = PurchaseReturnSettingsForm(obj=settings)
    if form.validate_on_submit():
        if not settings:
            settings = PurchaseReturnSettings()
            db.session.add(settings)
        settings.return_prefix = form.return_prefix.data or 'PRet-'
        settings.return_suffix = form.return_suffix.data or ''
        settings.next_number = form.next_number.data or 1
        db.session.commit()
        flash('Purchase return settings updated successfully.', 'success')
        return redirect(url_for('purchase.purchase_return_settings'))
    return render_template('purchase/purchase_return_settings.html', settings=settings, form=form)

@bp.route("/vendor/<int:id>/export/csv")
@login_required
def vendor_export_csv(id):
    """Export vendor profile to CSV"""
    vendor = Vendor.query.get_or_404(id)
    bills = sorted(vendor.bills, key=lambda b: b.date, reverse=True)
    advances = sorted(vendor.advances, key=lambda a: a.date, reverse=True)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Vendor info
    writer.writerow(["Vendor Profile Export"])
    writer.writerow(["Name", vendor.name])
    writer.writerow(["Email", vendor.email or ""])
    writer.writerow(["Phone", vendor.phone or ""])
    writer.writerow(["Address", vendor.address or ""])
    writer.writerow(["Payment Method", vendor.payment_method or ""])
    writer.writerow([])
    
    # Bills
    writer.writerow(["Purchase Bills"])
    writer.writerow(["Bill #", "Date", "Subtotal", "Tax", "Discount", "Total", "Paid", "Balance", "Status"])
    for bill in bills:
        writer.writerow([
            bill.bill_number,
            bill.date.strftime("%Y-%m-%d"),
            bill.subtotal,
            bill.tax,
            bill.discount,
            bill.total,
            bill.paid_amount,
            bill.balance_due,
            bill.status
        ])
    writer.writerow([])
    
    # Advances
    writer.writerow(["Advances"])
    writer.writerow(["Date", "Description", "Amount", "Status"])
    for adv in advances:
        writer.writerow([
            adv.date.strftime("%Y-%m-%d"),
            adv.description or "",
            adv.amount,
            "Adjusted" if adv.is_adjusted else "Pending"
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"vendor_{vendor.id}_{vendor.name}_profile.csv"
    )

@bp.route("/vendor/<int:id>/export/excel")
@login_required
def vendor_export_excel(id):
    """Export vendor profile to Excel"""
    vendor = Vendor.query.get_or_404(id)
    bills = sorted(vendor.bills, key=lambda b: b.date, reverse=True)
    advances = sorted(vendor.advances, key=lambda a: a.date, reverse=True)
    
    wb = openpyxl.Workbook()
    
    # Vendor Info sheet
    ws1 = wb.active
    ws1.title = "Vendor Info"
    ws1.append(["Vendor Profile Export"])
    ws1.append(["Name", vendor.name])
    ws1.append(["Email", vendor.email or ""])
    ws1.append(["Phone", vendor.phone or ""])
    ws1.append(["Address", vendor.address or ""])
    ws1.append(["Payment Method", vendor.payment_method or ""])
    
    # Bills sheet
    ws2 = wb.create_sheet("Purchase Bills")
    ws2.append(["Bill #", "Date", "Subtotal", "Tax", "Discount", "Total", "Paid", "Balance", "Status"])
    for bill in bills:
        ws2.append([
            bill.bill_number,
            bill.date.strftime("%Y-%m-%d"),
            bill.subtotal,
            bill.tax,
            bill.discount,
            bill.total,
            bill.paid_amount,
            bill.balance_due,
            bill.status
        ])
    
    # Advances sheet
    ws3 = wb.create_sheet("Advances")
    ws3.append(["Date", "Description", "Amount", "Status"])
    for adv in advances:
        ws3.append([
            adv.date.strftime("%Y-%m-%d"),
            adv.description or "",
            adv.amount,
            "Adjusted" if adv.is_adjusted else "Pending"
        ])
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"vendor_{vendor.id}_{vendor.name}_profile.xlsx"
    )

@bp.route("/vendor/<int:id>/export/pdf")
@login_required
def vendor_export_pdf(id):
    """Export vendor profile to PDF"""
    vendor = Vendor.query.get_or_404(id)
    bills = sorted(vendor.bills, key=lambda b: b.date, reverse=True)
    advances = sorted(vendor.advances, key=lambda a: a.date, reverse=True)
    
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle("CustomTitle", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#366092"), spaceAfter=12, alignment=TA_CENTER)
    title = Paragraph(f"Vendor Profile: {vendor.name}", title_style)
    elements.append(title)
    
    # Vendor Info
    info_data = [
        ["Name:", vendor.name],
        ["Email:", vendor.email or ""],
        ["Phone:", vendor.phone or ""],
        ["Address:", vendor.address or ""],
        ["Payment Method:", vendor.payment_method or ""]
    ]
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Bills Table
    elements.append(Paragraph("Purchase Bills", styles["Heading2"]))
    bill_data = [["Bill #", "Date", "Total", "Paid", "Balance", "Status"]]
    for bill in bills:
        bill_data.append([
            bill.bill_number,
            bill.date.strftime("%Y-%m-%d"),
            f"Rs {bill.total:,.2f}",
            f"Rs {bill.paid_amount:,.2f}",
            f"Rs {bill.balance_due:,.2f}",
            bill.status.title()
        ])
    
    if len(bill_data) > 1:
        bill_table = Table(bill_data, colWidths=[1.2*inch, 1*inch, 1*inch, 1*inch, 1*inch, 0.8*inch])
        bill_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#366092")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.lightgrey]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        elements.append(bill_table)
    
    elements.append(Spacer(1, 0.3*inch))
    
    # Advances Table
    elements.append(Paragraph("Advances", styles["Heading2"]))
    adv_data = [["Date", "Description", "Amount", "Status"]]
    for adv in advances:
        adv_data.append([
            adv.date.strftime("%Y-%m-%d"),
            adv.description or "",
            f"Rs {adv.amount:,.2f}",
            "Adjusted" if adv.is_adjusted else "Pending"
        ])
    
    if len(adv_data) > 1:
        adv_table = Table(adv_data, colWidths=[1*inch, 2.5*inch, 1*inch, 1*inch])
        adv_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#366092")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.lightgrey]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        elements.append(adv_table)
    
    doc.build(elements)
    output.seek(0)
    
    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"vendor_{vendor.id}_{vendor.name}_profile.pdf"
    )
