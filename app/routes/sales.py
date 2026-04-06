from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required
from app import db
from app.models import Sale, SaleItem, Product, Customer, Vendor, Company, InvoiceSettings, Currency
from app.forms import SaleForm, CustomerForm, InvoiceSettingsForm
from datetime import datetime
from sqlalchemy import func
from app.pdf_utils import generate_professional_pdf
import os
from werkzeug.utils import secure_filename

bp = Blueprint('sales', __name__)

@bp.route('/invoices')
@login_required
def invoices():
    status = request.args.get('status', 'all')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    
    query = Sale.query
    
    if status != 'all':
        query = query.filter(Sale.status == status)
    
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
    
    sales = query.order_by(Sale.date.desc()).all()
    
    # Calculate totals
    total_subtotal = sum(sale.subtotal for sale in sales)
    total_tax = sum(sale.tax for sale in sales)
    total_amount = sum(sale.total for sale in sales)
    total_paid = sum(sale.paid_amount for sale in sales)
    total_balance = sum(sale.balance_due for sale in sales)
    
    return render_template('sales/invoices.html', 
                         sales=sales, 
                         current_status=status,
                         from_date=from_date,
                         to_date=to_date,
                         total_subtotal=total_subtotal,
                         total_tax=total_tax,
                         total_amount=total_amount,
                         total_paid=total_paid,
                         total_balance=total_balance)

@bp.route('/invoice/create', methods=['GET', 'POST'])
@login_required
def create_invoice():
    form = SaleForm()
    customers = Customer.query.all()
    vendors = Vendor.query.all()
    products = Product.query.all()
    currencies = Currency.query.filter_by(is_active=True).all()
    
    form.customer_id.choices = [(0, 'Walk-in Customer')] + [(c.id, c.name) for c in customers]
    
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        selected_vendor_id = request.form.get('vendor_id')
        date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
        
        # Get items from form
        items = []
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        
        subtotal = 0
        sale_items = []
        
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                product = Product.query.get(int(product_ids[i]))
                quantity = float(quantities[i])
                price = float(prices[i])
                total = quantity * price
                subtotal += total
                
                sale_items.append({
                    'product_id': product.id,
                    'quantity': quantity,
                    'unit_price': price,
                    'total': total
                })
        
        tax_rate = float(request.form.get('tax_rate', 0))
        tax = subtotal * (tax_rate / 100)
        discount = float(request.form.get('discount', 0))
        total = subtotal + tax - discount
        
        # Generate invoice number
        last_invoice = Sale.query.order_by(Sale.id.desc()).first()
        invoice_number = f"INV-{datetime.now().strftime('%Y%m')}-{ (last_invoice.id + 1) if last_invoice else 1:04d}"
        
        sale = Sale(
            invoice_number=invoice_number,
            customer_id=customer_id if customer_id != '0' else None,
            vendor_id=selected_vendor_id if selected_vendor_id and selected_vendor_id != '0' else None,
            date=date,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax=tax,
            discount=discount,
            total=total,
            status=request.form.get('status', 'unpaid'),
            currency_id=request.form.get('currency_id', None),
            exchange_rate=float(request.form.get('exchange_rate', 1)),
            paid_amount=0
        )

        due_date_str = request.form.get('due_date')
        if due_date_str:
            try:
                sale.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                sale.due_date = None
        
        db.session.add(sale)
        db.session.flush()
        
        # Add items
        for item in sale_items:
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                total=item['total']
            )
            db.session.add(sale_item)
            
            # Update inventory
            product = Product.query.get(item['product_id'])
            product.update_quantity(-item['quantity'])
        
        db.session.commit()
        flash('Invoice created successfully!', 'success')
        return redirect(url_for('sales.invoice_detail', id=sale.id))
    
    return render_template('sales/create_invoice.html', form=form, products=products, customers=customers, vendors=vendors, currencies=currencies, now=datetime.now())

@bp.route('/invoice/<int:id>')
@login_required
def invoice_detail(id):
    sale = Sale.query.get_or_404(id)
    return render_template('sales/invoice_detail.html', sale=sale)

@bp.route('/invoice/<int:id>/delete', methods=['POST'])
@login_required
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

@bp.route('/invoice/<int:id>/pay', methods=['POST'])
@login_required
def pay_invoice(id):
    sale = Sale.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    
    if amount > 0:
        sale.paid_amount += amount
        if sale.paid_amount >= sale.total:
            sale.status = 'paid'
        else:
            sale.status = 'partial'
        
        db.session.commit()
        flash(f'Payment of ${amount} recorded successfully!', 'success')
    
    return redirect(url_for('sales.invoice_detail', id=sale.id))

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
        flash(f'Discount of Rs {discount_amount} applied successfully!', 'success')
    
    return redirect(request.referrer or url_for('sales.invoice_detail', id=sale.id))

@bp.route('/customers')
@login_required
def customers():
    customers = Customer.query.all()
    return render_template('sales/customers.html', customers=customers)


@bp.route('/customer/<int:id>')
@login_required
def customer_profile(id):
    customer = Customer.query.get_or_404(id)
    return render_template('sales/customer_profile.html', customer=customer)

@bp.route('/customer/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            gst_number=form.gst_number.data
        )
        db.session.add(customer)
        db.session.commit()
        flash('Customer added successfully!', 'success')
        return redirect(url_for('sales.customers'))
    
    return render_template('sales/add_customer.html', form=form)

@bp.route('/customer/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    form = CustomerForm(obj=customer)
    
    if form.validate_on_submit():
        customer.name = form.name.data
        customer.email = form.email.data
        customer.phone = form.phone.data
        customer.address = form.address.data
        customer.gst_number = form.gst_number.data
        db.session.commit()
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('sales.customers'))
    
    return render_template('sales/edit_customer.html', form=form, customer=customer)

@bp.route('/customer/<int:id>/delete', methods=['POST'])
@login_required
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


@bp.route('/invoice/<int:id>/pdf')
@login_required
def invoice_pdf(id):
    sale = Sale.query.get_or_404(id)
    company = Company.query.first()
    invoice_settings = InvoiceSettings.query.first()
    
    try:
        buffer = generate_professional_pdf('invoice', sale, company, invoice_settings)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"invoice_{sale.invoice_number or 'unknown'}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        # Log the error and return a user-friendly message
        print(f"PDF generation error: {str(e)}")
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('sales.invoice_detail', id=id))

@bp.route('/company', methods=['GET', 'POST'])
@login_required
def company_settings():
    company = Company.query.first()
    if not company:
        company = Company()
        db.session.add(company)
        db.session.commit()
    
    if request.method == 'POST':
        company.name = request.form.get('name')
        company.address = request.form.get('address')
        company.phone = request.form.get('phone')
        company.email = request.form.get('email')
        company.gst_number = request.form.get('gst_number')
        company.pan_number = request.form.get('pan_number')
        company.website = request.form.get('website')
        company.bank_name = request.form.get('bank_name')
        company.account_number = request.form.get('account_number')
        company.ifsc_code = request.form.get('ifsc_code')
        company.account_holder_name = request.form.get('account_holder_name')
        
        # Handle logo upload
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename:
                filename = secure_filename(logo_file.filename)
                logo_path = os.path.join('app', 'static', 'uploads', filename)
                os.makedirs(os.path.dirname(logo_path), exist_ok=True)
                logo_file.save(logo_path)
                company.logo_path = logo_path
        
        db.session.commit()
        flash('Company settings updated successfully!', 'success')
        return redirect(url_for('sales.company_settings'))
    
    return render_template('sales/company_settings.html', company=company)

@bp.route('/invoice/settings', methods=['GET', 'POST'])
@login_required
def invoice_settings():
    settings = InvoiceSettings.query.first()
    if not settings:
        settings = InvoiceSettings()
        db.session.add(settings)
        db.session.commit()
    
    form = InvoiceSettingsForm(obj=settings)
    
    if form.validate_on_submit():
        form.populate_obj(settings)
        db.session.commit()
        flash('Invoice settings updated successfully!', 'success')
        return redirect(url_for('sales.invoice_settings'))
    
    return render_template('sales/invoice_settings.html', form=form, settings=settings)