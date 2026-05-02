from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response, current_app
from flask_login import login_required, current_user
from app.utils import permission_required
from app import db
from app.models import Sale, SaleItem, Product, Customer, Vendor, Company, InvoiceSettings, Currency, CustomerAdvance, SaleReturn, Salesman, CustomerGroup, Payment, PaymentMethod, SalesmanGroup
from app.forms import SaleForm, CustomerForm, InvoiceSettingsForm, SalesmanForm, CustomerGroupForm
from datetime import datetime, date
from sqlalchemy import func, or_, and_
from app.pdf_utils import generate_professional_pdf
import os
from werkzeug.utils import secure_filename
from app.routes.filters import apply_saved_filter_to_query

bp = Blueprint('sales', __name__)

@bp.route('/invoices')
@login_required
def invoices():
    status = request.args.get('status', 'all')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    salesman_id = request.args.get('salesman_id', type=int)
    
    query = Sale.query
    
    if status == 'overdue':
        query = query.filter(
            Sale.status != 'paid',
            Sale.due_date < datetime.utcnow()
        )
    elif status != 'all':
        query = query.filter(Sale.status == status)
    
    if salesman_id:
        query = query.filter(Sale.salesman_id == salesman_id)
    
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
            query = query.filter(Sale.date >= from_date_obj)
        except ValueError:
            pass  # Invalid date format, ignore filter
    
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')
            # Add one day to include the end date
            to_date_obj = to_date_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(Sale.date <= to_date_obj)
        except ValueError:
            pass  # Invalid date format, ignore filter
    
    query = apply_saved_filter_to_query(query, 'sale', request.args)
    
    sales = query.order_by(Sale.date.desc()).all()
    
    # Calculate totals
    total_subtotal = sum(sale.subtotal for sale in sales)
    total_tax = sum(sale.tax for sale in sales)
    total_amount = sum(sale.total for sale in sales)
    total_paid = sum(sale.paid_amount for sale in sales)
    total_balance = sum(sale.balance_due for sale in sales)
    
    # Get company date format
    company = Company.query.first()
    date_format = company.date_format if company and company.date_format else '%Y-%m-%d'
    
        # Load salesmen for filter dropdown
    salesmen = Salesman.query.filter_by(is_active=True).all()
    
    return render_template('sales/invoices.html', 
                         sales=sales, 
                         current_status=status,
                         from_date=from_date,
                         to_date=to_date,
                         salesman_id=salesman_id,
                         salesmen=salesmen,
                         total_subtotal=total_subtotal,
                         total_tax=total_tax,
                         total_amount=total_amount,
                         total_paid=total_paid,
                         total_balance=total_balance,
                         date_format=date_format,
                         active_module='sale',
                         filter_id=request.args.get('filter_id'))

@bp.route('/invoice/create', methods=['GET', 'POST'])
@login_required
@permission_required('sales', action='add')
def create_invoice():
    form = SaleForm()
    customers = Customer.query.all()
    vendors = Vendor.query.all()
    products = Product.query.all()
    currencies = Currency.query.filter_by(is_active=True).all()
    
    customer_advances = {c.id: float(c.remaining_advance_balance) for c in customers}
    customer_total_advances = {c.id: float(c.total_advances_received) for c in customers}
    
    form.customer_id.choices = [(0, 'Walk-in Customer')] + [(c.id, c.name) for c in customers]
    form.salesman_id.choices = [(0, 'No Salesman')] + [(s.id, s.name) for s in Salesman.query.filter_by(is_active=True).all()]
    
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        selected_vendor_id = request.form.get('vendor_id')
        salesman_id = request.form.get('salesman_id')
        date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
        
        # Get items from form
        items = []
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        deliveries = request.form.getlist('delivery[]')
        
        subtotal = 0
        item_delivery_total = 0
        sale_items = []
        
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                product = Product.query.get(int(product_ids[i]))
                quantity = float(quantities[i])
                price = float(prices[i])
                delivery_fee = float(deliveries[i]) if i < len(deliveries) else 0
                item_subtotal = quantity * price
                total = item_subtotal + delivery_fee
                subtotal += total
                item_delivery_total += delivery_fee
                
                sale_items.append({
                    'product_id': product.id,
                    'quantity': quantity,
                    'unit_price': price,
                    'delivery_fee': delivery_fee,
                    'total': total
                })
        
        tax_rate = float(request.form.get('tax_rate', 0))
        tax = subtotal * (tax_rate / 100)
        discount = float(request.form.get('discount', 0))
        delivery_charge = float(request.form.get('delivery_charge', 0))
        advance_applied = float(request.form.get('advance_applied', 0))

        total = subtotal + tax + delivery_charge - discount - advance_applied

        # Generate invoice number using settings
        settings = InvoiceSettings.query.first()
        if not settings:
            settings = InvoiceSettings(invoice_prefix='INV-', invoice_suffix='', next_number=1)
            db.session.add(settings)
        invoice_number = f"{settings.invoice_prefix}{settings.next_number}{settings.invoice_suffix}"
        settings.next_number += 1

        sale = Sale(
            invoice_number=invoice_number,
            customer_id=customer_id if customer_id != '0' else None,
            vendor_id=selected_vendor_id if selected_vendor_id and selected_vendor_id != '0' else None,
            date=date,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax=tax,
            discount=discount,
            delivery_charge=delivery_charge,
            advance_applied=advance_applied,
            total=total,
            status=request.form.get('status', 'unpaid'),
            currency_id=request.form.get('currency_id', None),
            exchange_rate=float(request.form.get('exchange_rate', 1)),
            salesman_id=salesman_id if salesman_id and salesman_id != '0' else None,
            paid_amount=0,
            created_by=current_user.id
        )

        due_date_str = request.form.get('due_date')
        if due_date_str:
            try:
                sale.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                sale.due_date = None
        
        db.session.add(sale)
        db.session.flush()
        
        # Handle advance application - link to customer advances
        if customer_id and customer_id != '0' and advance_applied > 0:
            customer = Customer.query.get(int(customer_id))
            remaining_to_apply = advance_applied
            
            # Get advances sorted by date (oldest first)
            advances = CustomerAdvance.query.filter_by(customer_id=customer.id).filter(
                CustomerAdvance.is_adjusted == False
            ).order_by(CustomerAdvance.date).all()
            
            for adv in advances:
                if remaining_to_apply <= 0:
                    break
                    
                available = adv.remaining_balance
                if available > 0:
                    apply_amt = min(available, remaining_to_apply)
                    adv.applied_amount += apply_amt
                    remaining_to_apply -= apply_amt
                    
                    if adv.remaining_balance <= 0:
                        adv.is_adjusted = True
                        adv.adjusted_invoice_id = sale.id
        
        # Add items
        for item in sale_items:
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                delivery_fee=item.get('delivery_fee', 0),
                total=item['total']
            )
            db.session.add(sale_item)
            
            # Update inventory
            product = Product.query.get(item['product_id'])
            product.update_quantity(-item['quantity'])
        
        db.session.commit()
        flash('Invoice created successfully!', 'success')
        return redirect(url_for('sales.invoice_detail', id=sale.id))
    
    salesmen = Salesman.query.filter_by(is_active=True).all()
    return render_template('sales/create_invoice.html', form=form, products=products, customers=customers, vendors=vendors, currencies=currencies, now=datetime.now(), customer_advances=customer_advances, customer_total_advances=customer_total_advances, salesmen=salesmen)

@bp.route('/invoice/<int:id>')
@login_required
def invoice_detail(id):
    sale = Sale.query.get_or_404(id)
    company = Company.query.first()
    date_format = company.date_format if company and company.date_format else '%Y-%m-%d'
    returns = SaleReturn.query.filter_by(sale_id=sale.id).order_by(SaleReturn.date.desc()).all()
    # Get payment methods for dropdown and existing payments for display
    payment_methods = PaymentMethod.query.filter_by(is_active=True).order_by(PaymentMethod.name).all()
    payments = Payment.query.filter_by(invoice_id=sale.id).order_by(Payment.date.desc()).all()
    return render_template('sales/invoice_detail.html', sale=sale, returns=returns, date_format=date_format, payment_methods=payment_methods, payments=payments, today=datetime.utcnow().strftime('%Y-%m-%d'))

@bp.route('/invoice/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('sales', action='edit')
def edit_invoice(id):
    sale = Sale.query.get_or_404(id)
    form = SaleForm(obj=sale)
    customers = Customer.query.all()
    vendors = Vendor.query.all()
    products = Product.query.all()
    currencies = Currency.query.filter_by(is_active=True).all()
    salesmen = Salesman.query.filter_by(is_active=True).all()

    form.customer_id.choices = [(0, 'Walk-in Customer')] + [(c.id, c.name) for c in customers]
    form.salesman_id.choices = [(0, 'No Salesman')] + [(s.id, s.name) for s in salesmen]

    if request.method == 'POST':
        # Revert old inventory
        for item in sale.items:
            product = Product.query.get(item.product_id)
            if product:
                product.update_quantity(item.quantity)

        # Delete old items
        SaleItem.query.filter_by(sale_id=sale.id).delete()

        # Rebuild from form
        customer_id = request.form.get('customer_id')
        selected_vendor_id = request.form.get('vendor_id')
        salesman_id = request.form.get('salesman_id')
        date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        deliveries = request.form.getlist('delivery[]')

        subtotal = 0
        sale_items = []

        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                product = Product.query.get(int(product_ids[i]))
                quantity = float(quantities[i])
                price = float(prices[i])
                delivery_fee = float(deliveries[i]) if i < len(deliveries) else 0
                item_subtotal = quantity * price
                total = item_subtotal + delivery_fee
                subtotal += total

                sale_items.append({
                    'product_id': product.id,
                    'quantity': quantity,
                    'unit_price': price,
                    'delivery_fee': delivery_fee,
                    'total': total
                })

        tax_rate = float(request.form.get('tax_rate', 0))
        tax = subtotal * (tax_rate / 100)
        discount = float(request.form.get('discount', 0))
        delivery_charge = float(request.form.get('delivery_charge', 0))

        sale.customer_id = customer_id if customer_id != '0' else None
        sale.vendor_id = selected_vendor_id if selected_vendor_id and selected_vendor_id != '0' else None
        sale.salesman_id = salesman_id if salesman_id and salesman_id != '0' else None
        sale.date = date
        sale.subtotal = subtotal
        sale.tax_rate = tax_rate
        sale.tax = tax
        sale.discount = discount
        sale.delivery_charge = delivery_charge
        sale.advance_applied = float(request.form.get('advance_applied', sale.advance_applied or 0))
        sale.currency_id = request.form.get('currency_id') or None
        sale.exchange_rate = float(request.form.get('exchange_rate', 1))

        due_date_str = request.form.get('due_date')
        if due_date_str:
            try:
                sale.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                sale.due_date = None

        # Add items & update inventory
        for item in sale_items:
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                delivery_fee=item.get('delivery_fee', 0),
                total=item['total']
            )
            db.session.add(sale_item)
            product = Product.query.get(item['product_id'])
            product.update_quantity(-item['quantity'])

        sale.calculate_totals()
        # Preserve paid amount; update status accordingly
        sale.update_status()
        sale.updated_at = datetime.utcnow()

        db.session.commit()
        flash('Invoice updated successfully!', 'success')
        return redirect(url_for('sales.invoice_detail', id=sale.id))

    return render_template('sales/edit_invoice.html', form=form, sale=sale, products=products,
                           customers=customers, vendors=vendors, currencies=currencies,
                           salesmen=salesmen, now=datetime.now())


@bp.route('/invoice/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('sales', action='delete')
def delete_invoice(id):
    sale = Sale.query.get_or_404(id)
    # Restore inventory for sold items
    for item in sale.items:
        product = Product.query.get(item.product_id)
        if product:
            product.update_quantity(item.quantity)

    db.session.delete(sale)
    db.session.commit()
    flash('Invoice deleted successfully.', 'success')
    return redirect(url_for('sales.invoices'))

@bp.route('/invoices/bulk-delete', methods=['POST'])
@login_required
@permission_required('sales', action='delete')
def bulk_delete_invoices():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'message': 'No invoices selected'}), 400
    
    deleted_count = 0
    errors = []
    
    for invoice_id in ids:
        sale = Sale.query.get(invoice_id)
        if not sale:
            continue
            
        try:
            # Restore inventory
            for item in sale.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(item.quantity)
            
            db.session.delete(sale)
            deleted_count += 1
        except Exception as e:
            db.session.rollback()
            errors.append(f'Error deleting Invoice {sale.invoice_number}: {str(e)}')
            
    if deleted_count > 0:
        db.session.commit()
        
    message = f'Successfully deleted {deleted_count} invoices.'
    if errors:
        return jsonify({'success': False, 'message': message, 'errors': errors}), 500
    return jsonify({'success': True, 'message': message})

@bp.route('/invoice/<int:id>/pay', methods=['POST'])
@login_required
def pay_invoice(id):
    sale = Sale.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    
    if amount > 0:
        # Update sale payment status (existing logic preserved)
        sale.paid_amount += amount
        sale.update_status()
        
        # Handle payment receipt image upload
        image_path = None
        if 'payment_image' in request.files:
            payment_file = request.files['payment_image']
            if payment_file and payment_file.filename:
                filename = secure_filename(payment_file.filename)
                upload_dir = os.path.join('app', 'static', 'uploads', 'sale_payments')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                payment_file.save(file_path)
                image_path = file_path.replace('\\', '/')
        
        # Create Payment record for history tracking
        payment_date_str = request.form.get('payment_date', '')
        payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d') if payment_date_str else datetime.utcnow()
        payment_method = request.form.get('payment_method', 'Cash')
        payment_notes = request.form.get('payment_notes', '')
        
        # Generate payment number
        last_payment = Payment.query.order_by(Payment.id.desc()).first()
        payment_num = f"PAY-{last_payment.id + 1 if last_payment else 1}"
        
        payment = Payment(
            payment_number=payment_num,
            date=payment_date,
            amount=amount,
            method=payment_method,
            invoice_id=sale.id,
            notes=payment_notes,
            image_path=image_path,
            created_by=current_user.id
        )
        db.session.add(payment)
        
        db.session.commit()
        flash(f'Payment of PKR {amount:,.2f} recorded successfully!', 'success')
    
    return redirect(url_for('sales.invoice_detail', id=sale.id))


@bp.route('/invoice/<int:id>/payment/<int:pay_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('sales', action='edit')
def edit_payment(id, pay_id):
    """Edit existing payment for sales invoice"""
    sale = Sale.query.get_or_404(id)
    payment = Payment.query.filter_by(id=pay_id, invoice_id=sale.id).first_or_404()

    if request.method == 'POST':
        old_amount = payment.amount

        # Update payment details
        payment_date_str = request.form.get('payment_date')
        if payment_date_str:
            try:
                payment.date = datetime.strptime(payment_date_str, '%Y-%m-%d')
            except ValueError:
                payment.date = datetime.utcnow()
        else:
            payment.date = datetime.utcnow()

        payment.method = request.form.get('payment_method', 'Cash')
        # Only update reference_number if provided
        if 'reference_number' in request.form:
            payment.reference_number = request.form.get('reference_number', '')
        payment.notes = request.form.get('payment_notes', '')

        new_amount = float(request.form.get('amount', 0))

        # Handle image update
        if 'payment_image' in request.files:
            payment_file = request.files['payment_image']
            if payment_file and payment_file.filename:
                filename = secure_filename(payment_file.filename)
                upload_dir = os.path.join('app', 'static', 'uploads', 'sale_payments')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                payment_file.save(file_path)
                payment.image_path = file_path.replace('\\', '/')

        # IMPORTANT: Update payment amount BEFORE calculating delta effect on sale
        payment.amount = new_amount

        # Safe paid_amount update: adjust sale's paid_amount by the difference
        delta = new_amount - old_amount
        from app.utils import safe_update_paid_amount
        safe_update_paid_amount(sale, delta)

        db.session.commit()
        flash(f'Payment updated: PKR{new_amount:,.2f} ({payment.method})', 'success')
        return redirect(url_for('sales.invoice_detail', id=sale.id))

    # GET: render edit form
    return render_template('sales/edit_payment.html', payment=payment, sale=sale)


@bp.route('/invoice/<int:id>/payment/<int:pay_id>/delete', methods=['POST'])
@login_required
@permission_required('sales', action='delete')
def delete_payment(id, pay_id):
    """Safely delete payment: reverse paid_amount, cleanup transactions"""
    sale = Sale.query.get_or_404(id)
    payment = Payment.query.filter_by(id=pay_id, invoice_id=sale.id).first_or_404()
    
    # Reverse from sale
    delta = -payment.amount
    from app.utils import safe_update_paid_amount
    safe_update_paid_amount(sale, delta)
    
    # Delete linked accounting transactions
    from app.utils import cleanup_linked_transactions
    cleanup_linked_transactions(payment)
    
    # Delete old image if exists
    if payment.image_path:
        try:
            image_path = os.path.join(current_app.root_path, 'static', payment.image_path)
            if os.path.exists(image_path):
                os.remove(image_path)
        except:
            pass
    
    db.session.delete(payment)
    db.session.commit()
    flash(f'Payment deleted. Balance updated.', 'success')
    return redirect(url_for('sales.invoice_detail', id=sale.id))


@bp.route('/payment/<int:payment_id>/image')
@login_required
def payment_image(payment_id):
    """Serve payment receipt image"""
    from flask import current_app
    payment = Payment.query.get_or_404(payment_id)
    if payment.image_path:
        # Stored path is relative to project root (e.g., 'app/static/uploads/sale_payments/xxx.png')
        if os.path.isabs(payment.image_path):
            file_path = payment.image_path
        else:
            project_root = os.path.dirname(current_app.root_path)
            file_path = os.path.join(project_root, payment.image_path)
        if os.path.exists(file_path):
            return send_file(file_path)
    flash('Image not found', 'error')
    return redirect(url_for('sales.invoice_detail', id=payment.invoice_id))

@bp.route('/invoice/<int:id>/discount', methods=['POST'])
@login_required
def apply_discount(id):
    sale = Sale.query.get_or_404(id)
    discount_amount = float(request.form.get('discount_amount', 0))
    
    if discount_amount > 0:
        # Check if the discount is larger than the total
        # Ensure we don't end up with a negative total
        sale.discount += discount_amount
        sale.calculate_totals()
        sale.update_status()
        
        db.session.commit()
        flash(f'Discount of PKR {discount_amount} applied successfully!', 'success')
    
    return redirect(request.referrer or url_for('sales.invoice_detail', id=sale.id))

@bp.route('/customers')
@login_required
def customers():
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    customer_id = request.args.get('customer_id', type=int)
    
    query = Customer.query
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    if customer_id:
        query = query.filter_by(id=customer_id)
    elif search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Customer.name.ilike(search_filter)) |
            (Customer.email.ilike(search_filter)) |
            (Customer.phone.ilike(search_filter))
        )
    
    query = apply_saved_filter_to_query(query, 'customer', request.args)
    
    customers = query.order_by(Customer.name.asc()).all()
    # List of all customers for the searchable dropdown
    all_customers = Customer.query.order_by(Customer.name.asc()).all()
    
    return render_template('sales/customers.html', 
                         customers=customers, 
                         all_customers=all_customers,
                         current_status=status, 
                         search_query=search,
                         selected_customer_id=customer_id,
                         active_module='customer',
                         filter_id=request.args.get('filter_id'))

@bp.route('/customer/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload_customer():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('sales.bulk_upload_customer'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('sales.bulk_upload_customer'))
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('Please upload an Excel file (.xlsx or .xls)', 'error')
            return redirect(url_for('sales.bulk_upload_customer'))
        
        try:
            from openpyxl import load_workbook
            from io import BytesIO
            file_content = file.read()
            wb = load_workbook(filename=BytesIO(file_content), read_only=True)
            ws = wb.active
            rows = list(ws.values)
            if not rows:
                flash('File is empty', 'error')
                return redirect(url_for('sales.bulk_upload_customer'))
            headers = [str(h) if h else '' for h in rows[0]]
            df_data = []
            for row in rows[1:]:
                row_dict = {}
                for i, val in enumerate(row):
                    if i < len(headers):
                        row_dict[headers[i]] = val
                df_data.append(row_dict)
            import pandas as pd
            df = pd.DataFrame(df_data)
            
            required_columns = ['name']
            missing = [col for col in required_columns if col not in df.columns]
            if missing:
                flash(f'Missing required columns: {", ".join(missing)}', 'error')
                return redirect(url_for('sales.bulk_upload_customer'))
            
            added = 0
            errors = []
            
            for idx, row in df.iterrows():
                try:
                    name = str(row.get('name', '')).strip()
                    
                    if not name:
                        errors.append(f'Row {idx + 2}: Missing name')
                        continue
                    
                    customer = Customer(
                        name=name,
                        email=str(row.get('email', '')).strip() if pd.notna(row.get('email')) else None,
                        phone=str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else None,
                        address=str(row.get('address', '')).strip() if pd.notna(row.get('address')) else None,
                        gst_number=str(row.get('gst_number', '')).strip() if pd.notna(row.get('gst_number')) else None,
                        pan_number=str(row.get('pan_number', '')).strip() if pd.notna(row.get('pan_number')) else None,
                        contact_person=str(row.get('contact_person', '')).strip() if pd.notna(row.get('contact_person')) else None,
                    )
                    
                    db.session.add(customer)
                    added += 1
                except Exception as e:
                    errors.append(f'Row {idx + 2}: {str(e)}')
            
            db.session.commit()
            
            if added > 0:
                flash(f'Successfully added {added} customers!', 'success')
            if errors:
                flash(f'Errors: {"; ".join(errors[:10])}', 'warning')
            
            return redirect(url_for('sales.customers'))
            
        except Exception as e:
            flash(f'Error reading file: {str(e)}', 'error')
            return redirect(url_for('sales.bulk_upload_customer'))
    
    return render_template('sales/bulk_upload_customer.html')

@bp.route('/customer/download-sample')
@login_required
def download_customer_sample():
    try:
        from openpyxl import Workbook
        from io import BytesIO
        from flask import send_file
        
        wb = Workbook()
        ws = wb.active
        ws.title = 'Customers'
        
        headers = ['name', 'email', 'phone', 'address', 'gst_number', 'pan_number', 'contact_person']
        ws.append(headers)
        
        sample_data = [
            ['Customer A', 'customerA@example.com', '1234567890', '123 Main St, City', 'GST123456789', 'ABCDE1234F', 'John Doe'],
            ['Customer B', 'customerB@example.com', '2345678901', '456 Oak Ave, Town', 'GST987654321', 'FGHI5678K', 'Jane Smith'],
            ['Customer C', 'customerC@example.com', '3456789012', '789 Pine Rd, Village', '', '', '']
        ]
        
        for row in sample_data:
            ws.append(row)
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, download_name='sample_customers.xlsx', as_attachment=True)
        
    except Exception as e:
        flash(f'Error creating sample: {str(e)}', 'error')
        return redirect(url_for('sales.customers'))


@bp.route('/customer/<int:id>')
@login_required
def customer_profile(id):
    customer = Customer.query.get_or_404(id)
    # Sort sales newest first
    sales = sorted(customer.sales, key=lambda s: s.date, reverse=True)
    # Sort advances newest first
    advances = sorted(customer.advances, key=lambda a: a.date, reverse=True)
    return render_template('sales/customer_profile.html', 
                          customer=customer, 
                          sales=sales, 
                          advances=advances,
                          now=datetime.now())

@bp.route('/customer/<int:id>/advances-json')
@login_required
def customer_advances_json(id):
    customer = Customer.query.get_or_404(id)
    advances = CustomerAdvance.query.filter_by(customer_id=id).order_by(CustomerAdvance.date.desc()).all()
    return jsonify({
        'advances': [{
            'date': a.date.strftime('%d-%b-%Y'),
            'amount': a.amount,
            'applied': a.applied_amount,
            'balance': a.remaining_balance
        } for a in advances]
    })

@bp.route('/customer/add', methods=['GET', 'POST'])
@login_required
@permission_required('sales', action='add')
def add_customer():
    form = CustomerForm()
    groups = CustomerGroup.query.filter_by(is_active=True).all()
    form.group_id.choices = [(0, '- Select Group -')] + [(g.id, g.name) for g in groups]
    
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            company_name=form.company_name.data,
            group_id=form.group_id.data if form.group_id.data != 0 else None,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            gst_number=form.gst_number.data,
            payment_method=form.payment_method.data
        )
        db.session.add(customer)
        db.session.commit()
        flash('Customer added successfully!', 'success')
        return redirect(url_for('sales.customers'))
    
    return render_template('sales/add_customer.html', form=form)

@bp.route('/customer/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('sales', action='edit')
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    form = CustomerForm(obj=customer)
    groups = CustomerGroup.query.filter_by(is_active=True).all()
    form.group_id.choices = [(0, '- Select Group -')] + [(g.id, g.name) for g in groups]
    
    if form.validate_on_submit():
        customer.name = form.name.data
        customer.company_name = form.company_name.data
        customer.group_id = form.group_id.data if form.group_id.data != 0 else None
        customer.email = form.email.data
        customer.phone = form.phone.data
        customer.address = form.address.data
        customer.gst_number = form.gst_number.data
        customer.payment_method = form.payment_method.data
        db.session.commit()
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('sales.customers'))
    
    return render_template('sales/edit_customer.html', form=form, customer=customer)

@bp.route('/customer/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('sales', action='delete')
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    
    # Check if customer has associated records (Sales)
    if customer.sales:
        flash('Cannot delete customer as they have associated sales records.', 'danger')
        return redirect(url_for('sales.customers'))

    db.session.delete(customer)
    db.session.commit()
    flash('Customer deleted successfully!', 'success')
    return redirect(url_for('sales.customers'))

@bp.route('/customers/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_customers():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'message': 'No customers selected'}), 400
    
    deleted_count = 0
    skipped_count = 0
    errors = []
    
    for customer_id in ids:
        customer = Customer.query.get(customer_id)
        if not customer:
            continue
            
        # Check associations
        if customer.sales:
            skipped_count += 1
            continue
            
        try:
            db.session.delete(customer)
            deleted_count += 1
        except Exception as e:
            db.session.rollback()
            errors.append(f'Error deleting Customer {customer.name}: {str(e)}')
            
    if deleted_count > 0:
        db.session.commit()
        
    message = f'Successfully deleted {deleted_count} customers.'
    if skipped_count > 0:
        message += f' Skipped {skipped_count} customers with associated records.'
    
    if errors:
        return jsonify({'success': False, 'message': message, 'errors': errors}), 500
    return jsonify({'success': True, 'message': message})


@bp.route('/invoice/<int:id>/pdf')
@login_required
def invoice_pdf(id):
    sale = Sale.query.get_or_404(id)
    company = Company.query.first()
    invoice_settings = InvoiceSettings.query.first()
    
    try:
        buffer = generate_professional_pdf('invoice', sale, company, invoice_settings)
        
        response = make_response(buffer)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="invoice_{sale.invoice_number or "unknown"}.pdf"'
        return response
    except Exception as e:
        print(f"PDF generation error: {str(e)}")
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('sales.invoice_detail', id=id))

@bp.route('/invoice/<int:id>/pdf/view')
@login_required
def invoice_pdf_view(id):
    """View PDF inline (for sharing)"""
    sale = Sale.query.get_or_404(id)
    company = Company.query.first()
    invoice_settings = InvoiceSettings.query.first()
    
    try:
        buffer = generate_professional_pdf('invoice', sale, company, invoice_settings)
        
        response = make_response(buffer)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="{sale.invoice_number}.pdf"'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('sales.invoice_detail', id=id))

@bp.route('/invoice/<int:id>/pdf/share')
@login_required
def invoice_pdf_share(id):
    """Generate PDF, save to public folder, and return shareable link"""
    from flask import current_app
    import os
    import secrets
    
    sale = Sale.query.get_or_404(id)
    company = Company.query.first()
    invoice_settings = InvoiceSettings.query.first()
    
    try:
        buffer = generate_professional_pdf('invoice', sale, company, invoice_settings)
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        
        # Save to public folder
        public_dir = os.path.join(current_app.root_path, 'static', 'shared_pdfs')
        os.makedirs(public_dir, exist_ok=True)
        
        # Generate unique filename
        token = secrets.token_urlsafe(8)
        filename = f"invoice_{sale.invoice_number or 'unknown'}_{token}.pdf"
        filepath = os.path.join(public_dir, filename)
        
        # Save buffer to file
        with open(filepath, 'wb') as f:
            f.write(pdf_data)
        
        # Return the shareable URL
        share_url = url_for('static', filename=f'shared_pdfs/{filename}')
        return {'share_url': share_url, 'download_url': url_for('sales.invoice_pdf', id=id)}
    except Exception as e:
        return {'error': str(e)}, 500

@bp.route('/company', methods=['GET', 'POST'])
@login_required
def company_settings():
    company = Company.query.first()

    if request.method == 'POST':
        # Get name from form - required field
        company_name = request.form.get('name')
        if not company_name:
            flash('Company name is required.', 'error')
            return redirect(url_for('sales.company_settings'))

        if not company:
            company = Company(name=company_name)
            db.session.add(company)
        else:
            company.name = company_name

        company.address = request.form.get('address')
        company.phone = request.form.get('phone')
        company.email = request.form.get('email')
        company.gst_number = request.form.get('gst_number')
        company.pan_number = request.form.get('pan_number')
        company.website = request.form.get('website')
        company.date_format = request.form.get('date_format', '%Y-%m-%d')
        company.mo_prefix = request.form.get('mo_prefix', 'MO-')
        company.mo_suffix = request.form.get('mo_suffix', '')
        company.next_mo_number = request.form.get('next_mo_number', 1, type=int)
        company.bank_name = request.form.get('bank_name')
        company.account_number = request.form.get('account_number')
        company.ifsc_code = request.form.get('ifsc_code')
        company.account_holder_name = request.form.get('account_holder_name')

        # Handle logo upload
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename:
                # Validate file type
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
                filename = secure_filename(logo_file.filename)
                ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
                if ext not in allowed_extensions:
                    flash('Invalid file type for logo. Only PNG, JPG, JPEG, GIF allowed.', 'error')
                    return redirect(url_for('sales.company_settings'))
                # Save file
                upload_dir = os.path.join('app', 'static', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                logo_path = os.path.join(upload_dir, filename)
                logo_file.save(logo_path)
                # Store path
                company.logo_path = logo_path

        # Handle signature upload
        if 'signature' in request.files:
            sig_file = request.files['signature']
            if sig_file and sig_file.filename:
                # Validate file type
                allowed_extensions = {'png', 'jpg', 'jpeg'}
                filename = secure_filename(sig_file.filename)
                ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
                if ext not in allowed_extensions:
                    flash('Invalid file type for signature. Only PNG, JPG, JPEG allowed.', 'error')
                    return redirect(url_for('sales.company_settings'))
                # Save file
                upload_dir = os.path.join('app', 'static', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                sig_path = os.path.join(upload_dir, filename)
                sig_file.save(sig_path)
                company.signature_path = sig_path

        # Handle logo removal
        if request.form.get('remove_logo') == 'on' and company.logo_path:
            try:
                logo_file_path = company.logo_path
                if os.path.exists(logo_file_path):
                    os.remove(logo_file_path)
            except Exception:
                pass  # Ignore deletion errors
            company.logo_path = None

        # Handle signature removal
        if request.form.get('remove_signature') == 'on' and company.signature_path:
            try:
                sig_file_path = company.signature_path
                if os.path.exists(sig_file_path):
                    os.remove(sig_file_path)
            except Exception:
                pass  # Ignore deletion errors
            company.signature_path = None

        db.session.commit()
        flash('Company settings updated successfully!', 'success')
        return redirect(url_for('sales.company_settings'))

    return render_template('sales/company_settings.html', company=company)

@bp.route('/invoice/settings', methods=['GET', 'POST'])
@login_required
def invoice_settings():
    settings = InvoiceSettings.query.first()
    
    form = InvoiceSettingsForm(obj=settings)
    
    if form.validate_on_submit():
        if not settings:
            settings = InvoiceSettings()
            db.session.add(settings)
        
        settings.default_notes = form.default_notes.data
        settings.default_terms = form.default_terms.data
        settings.bank_name = form.bank_name.data
        settings.account_holder_name = form.account_holder_name.data
        settings.account_number = form.account_number.data
        settings.ifsc_code = form.ifsc_code.data
        settings.swift_code = form.swift_code.data
        settings.bank_address = form.bank_address.data
        settings.payment_instructions = form.payment_instructions.data
        settings.invoice_prefix = form.invoice_prefix.data or ''
        settings.invoice_suffix = form.invoice_suffix.data or ''
        settings.next_number = form.next_number.data or 1
        settings.tax_name = form.tax_name.data
        settings.tax_rate = form.tax_rate.data
        settings.payment_terms = form.payment_terms.data
        settings.notes = form.notes.data
        
        db.session.commit()
        flash('Invoice settings updated successfully.', 'success')
        return redirect(url_for('sales.invoice_settings'))
    
    return render_template('sales/invoice_settings.html', settings=settings, form=form)


# ===== CUSTOMER ADVANCE ROUTES =====

@bp.route('/customer/<int:id>/advance', methods=['POST'])
@login_required
def customer_receive_advance(id):
    """Record a quick advance payment received from a customer against material."""
    customer = Customer.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    description = request.form.get('description', '').strip()
    advance_date_str = request.form.get('advance_date', '')
    
    if amount <= 0:
        flash('Advance amount must be greater than zero.', 'danger')
        return redirect(url_for('sales.customer_profile', id=id))
    
    try:
        advance_date = datetime.strptime(advance_date_str, '%Y-%m-%d').date() if advance_date_str else date.today()
    except ValueError:
        advance_date = date.today()
    
    advance = CustomerAdvance(
        customer_id=customer.id,
        amount=amount,
        date=advance_date,
        description=description or 'Advance for purchase',
        created_by=current_user.id
    )
    db.session.add(advance)
    db.session.commit()
    flash(f'Advance of PKR {amount:,.2f} recorded from {customer.name}.', 'success')
    return redirect(url_for('sales.customer_profile', id=id))


@bp.route('/customer/<int:customer_id>/advance/<int:adv_id>/apply', methods=['POST'])
@login_required
def customer_apply_advance(customer_id, adv_id):
    """Apply a customer advance against a specific invoice."""
    advance = CustomerAdvance.query.get_or_404(adv_id)
    invoice_id = request.form.get('invoice_id')
    
    # Check if advance still has remaining balance
    if advance.remaining_balance <= 0:
        flash('This advance has no remaining balance to apply.', 'warning')
        return redirect(url_for('sales.customer_profile', id=customer_id))
    
    invoice = Sale.query.get_or_404(invoice_id)
    
    # Ensure the invoice belongs to the customer
    if invoice.customer_id != customer_id:
        flash('Invalid invoice for this customer.', 'danger')
        return redirect(url_for('sales.customer_profile', id=customer_id))
    
    # Check invoice balance
    if invoice.balance_due <= 0:
        flash('This invoice has no balance to apply advance against.', 'warning')
        return redirect(url_for('sales.customer_profile', id=customer_id))
    
    # Calculate how much to apply (minimum of advance balance and invoice balance)
    apply_amount = min(advance.remaining_balance, invoice.balance_due)
    
    # Update advance
    advance.applied_amount += apply_amount
    if advance.remaining_balance <= 0:
        advance.is_adjusted = True
        advance.adjusted_invoice_id = invoice.id
    
    # Update invoice advance applied
    invoice.advance_applied = (invoice.advance_applied or 0) + apply_amount
    
    # Recalculate invoice total
    invoice.calculate_totals()
    invoice.paid_amount += apply_amount
    invoice.update_status()
    
    db.session.commit()
    flash(f'Advance of PKR {apply_amount:,.2f} applied to invoice {invoice.invoice_number}.', 'success')
    return redirect(url_for('sales.customer_profile', id=customer_id))


@bp.route('/customer/<int:customer_id>/advance/<int:adv_id>/delete', methods=['POST'])
@login_required
@permission_required('sales', action='delete')
def customer_delete_advance(customer_id, adv_id):
    """Delete a customer advance. If applied, first unapplies from invoices."""
    advance = CustomerAdvance.query.get_or_404(adv_id)
    
    if advance.customer_id != customer_id:
        flash('Invalid advance for this customer.', 'danger')
        return redirect(url_for('sales.customer_profile', id=customer_id))
    
    # If advance has been applied, unapply it first
    if advance.applied_amount > 0:
        from app.models import Sale
        invoices_with_advance = Sale.query.filter(
            Sale.customer_id == customer_id,
            Sale.advance_applied > 0
        ).all()
        
        reverse_amount = advance.applied_amount
        
        for invoice in invoices_with_advance:
            if reverse_amount <= 0:
                break
            if invoice.advance_applied > 0:
                reverse_amt = min(invoice.advance_applied, reverse_amount)
                invoice.advance_applied -= reverse_amt
                invoice.calculate_totals()
                invoice.paid_amount -= reverse_amt
                invoice.update_status()
                reverse_amount -= reverse_amt
        
        advance.applied_amount = 0
        advance.is_adjusted = False
        advance.adjusted_invoice_id = None
    
    customer_name = advance.customer.name
    amount = advance.amount
    
    db.session.delete(advance)
    db.session.commit()
    flash(f'Advance of PKR {amount:,.2f} from {customer_name} has been deleted.', 'success')
    return redirect(url_for('sales.customer_profile', id=customer_id))


@bp.route('/customer/<int:customer_id>/advance/<int:adv_id>/unapply', methods=['POST'])
@login_required
def customer_unapply_advance(customer_id, adv_id):
    """Unapply/reverse an advance that was applied to an invoice."""
    advance = CustomerAdvance.query.get_or_404(adv_id)
    
    if advance.customer_id != customer_id:
        flash('Invalid advance for this customer.', 'danger')
        return redirect(url_for('sales.customer_profile', id=customer_id))
    
    if advance.applied_amount <= 0:
        flash('This advance has not been applied to any invoice.', 'warning')
        return redirect(url_for('sales.customer_profile', id=customer_id))
    
    # Find invoices that have this advance applied
    from app.models import Sale
    invoices_with_advance = Sale.query.filter(
        Sale.customer_id == customer_id,
        Sale.advance_applied > 0
    ).all()
    
    # Reverse the applied amount from invoices
    reverse_amount = advance.applied_amount
    
    for invoice in invoices_with_advance:
        if reverse_amount <= 0:
            break
        if invoice.advance_applied > 0:
            reverse_amt = min(invoice.advance_applied, reverse_amount)
            invoice.advance_applied -= reverse_amt
            invoice.calculate_totals()
            invoice.paid_amount -= reverse_amt
            invoice.update_status()
            reverse_amount -= reverse_amt
    
    # Reset advance
    advance.applied_amount = 0
    advance.is_adjusted = False
    advance.adjusted_invoice_id = None
    
    db.session.commit()
    flash(f'Advance of PKR {advance.amount:,.2f} has been unapplied from invoices.', 'success')
    return redirect(url_for('sales.customer_profile', id=customer_id))


# --- Salesman Management ---

@bp.route('/salesmen')
@login_required
def salesmen_list():
    salesmen = Salesman.query.all()
    return render_template('sales/salesmen.html', salesmen=salesmen)

@bp.route('/salesman/add', methods=['GET', 'POST'])
@login_required
@permission_required('sales', action='add')
def add_salesman():
    form = SalesmanForm()
    groups = SalesmanGroup.query.filter_by(is_active=True).all()
    form.group_id.choices = [(0, '- Select Group -')] + [(g.id, g.name) for g in groups]
    
    if form.validate_on_submit():
        salesman = Salesman(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            commission_rate=form.commission_rate.data,
            group_id=form.group_id.data if form.group_id.data != 0 else None,
            is_active=form.is_active.data
        )
        db.session.add(salesman)
        db.session.commit()
        flash('Salesman added successfully!', 'success')
        return redirect(url_for('sales.salesmen_list'))
    return render_template('sales/salesman_form.html', form=form, title='Add Salesman')

@bp.route('/salesman/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('sales', action='edit')
def edit_salesman(id):
    salesman = Salesman.query.get_or_404(id)
    form = SalesmanForm(obj=salesman)
    groups = SalesmanGroup.query.filter_by(is_active=True).all()
    form.group_id.choices = [(0, '- Select Group -')] + [(g.id, g.name) for g in groups]
    
    if form.validate_on_submit():
        salesman.name = form.name.data
        salesman.email = form.email.data
        salesman.phone = form.phone.data
        salesman.address = form.address.data
        salesman.commission_rate = form.commission_rate.data
        salesman.group_id = form.group_id.data if form.group_id.data != 0 else None
        salesman.is_active = form.is_active.data
        db.session.commit()
        flash('Salesman updated successfully!', 'success')
        return redirect(url_for('sales.salesmen_list'))
    return render_template('sales/salesman_form.html', form=form, title='Edit Salesman', salesman=salesman)

@bp.route('/salesman/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('sales', action='delete')
def delete_salesman(id):
    salesman = Salesman.query.get_or_404(id)
    if salesman.sales:
        flash('Cannot delete salesman with associated sales records.', 'danger')
        return redirect(url_for('sales.salesmen_list'))
    db.session.delete(salesman)
    db.session.commit()
    flash('Salesman deleted successfully.', 'info')
    return redirect(url_for('sales.salesmen_list'))

@bp.route('/salesman/quick-add', methods=['POST'])
@login_required
def quick_add_salesman():
    name = request.form.get('name')
    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400
    
    group_id = request.form.get('group_id')
    
    salesman = Salesman(name=name, group_id=group_id if group_id and group_id != '0' else None)
    db.session.add(salesman)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'salesman': {
            'id': salesman.id,
            'name': salesman.name
        }
    })

@bp.route('/salesman/group/quick-add', methods=['POST'])
@login_required
def quick_add_salesman_group():
    name = request.form.get('name')
    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400
    
    if SalesmanGroup.query.filter_by(name=name).first():
        return jsonify({'success': False, 'message': 'Group already exists'}), 400

    group = SalesmanGroup(name=name)
    db.session.add(group)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'group': {
            'id': group.id,
            'name': group.name
        }
    })

# --- Customer Group Management ---

@bp.route('/customer-groups')
@login_required
def customer_groups_list():
    groups = CustomerGroup.query.all()
    return render_template('sales/customer_groups.html', groups=groups)

@bp.route('/customer-group/add', methods=['GET', 'POST'])
@login_required
@permission_required('sales', action='add')
def add_customer_group():
    form = CustomerGroupForm()
    if form.validate_on_submit():
        group = CustomerGroup(
            name=form.name.data,
            description=form.description.data
        )
        db.session.add(group)
        db.session.commit()
        flash('Customer Group added successfully!', 'success')
        return redirect(url_for('sales.customer_groups_list'))
    return render_template('sales/customer_group_form.html', form=form, title='Add Customer Group')

@bp.route('/customer-group/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('sales', action='edit')
def edit_customer_group(id):
    group = CustomerGroup.query.get_or_404(id)
    form = CustomerGroupForm(obj=group)
    if form.validate_on_submit():
        group.name = form.name.data
        group.description = form.description.data
        db.session.commit()
        flash('Customer Group updated successfully!', 'success')
        return redirect(url_for('sales.customer_groups_list'))
    return render_template('sales/customer_group_form.html', form=form, title='Edit Customer Group', group=group)

@bp.route('/customer-group/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('sales', action='delete')
def delete_customer_group(id):
    group = CustomerGroup.query.get_or_404(id)
    if group.customers:
        flash('Cannot delete group with associated customers.', 'danger')
        return redirect(url_for('sales.customer_groups_list'))
    db.session.delete(group)
    db.session.commit()
    flash('Customer Group deleted successfully.', 'info')
    return redirect(url_for('sales.customer_groups_list'))

@bp.route('/customer-group/quick-add', methods=['POST'])
@login_required
def quick_add_customer_group():
    name = request.form.get('name')
    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400
    
    if CustomerGroup.query.filter_by(name=name).first():
        return jsonify({'success': False, 'message': 'Group already exists'}), 400

    group = CustomerGroup(name=name)
    db.session.add(group)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'group': {
            'id': group.id,
            'name': group.name
        }
    })
