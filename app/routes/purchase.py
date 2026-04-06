from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from app import db
from app.models import PurchaseBill, PurchaseItem, Product, Vendor, Company, Currency
from app.forms import PurchaseForm, VendorForm
from datetime import datetime, timedelta
from app.pdf_utils import generate_professional_pdf
import os

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
    
    return render_template('purchase/bills.html', 
                         bills=bills, 
                         current_status=status,
                         from_date=from_date,
                         to_date=to_date,
                         search=search,
                         total_amount=total_amount,
                         total_paid=total_paid,
                         total_balance=total_balance)

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
        
        # Generate bill number
        last_bill = PurchaseBill.query.order_by(PurchaseBill.id.desc()).first()
        bill_number = f"PO-{datetime.now().strftime('%Y%m')}-{(last_bill.id + 1) if last_bill else 1:04d}"
        
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

        # Add items
        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
                prod_id = int(product_ids[i])
                qty = float(quantities[i])
                price = float(prices[i])
                
                item = PurchaseItem(
                    product_id=prod_id,
                    quantity=qty,
                    unit_price=price,
                    total=qty * price
                )
                bill.items.append(item)
                
                # Update inventory (increase stock)
                product = Product.query.get(prod_id)
                if product:
                    product.update_quantity(qty)
        
        bill.calculate_totals()
        
        # Update paid amount from "Advance Paid" field in template
        advance = float(request.form.get('advance', 0))
        bill.paid_amount = advance
        if bill.paid_amount >= bill.total:
            bill.status = 'paid'
        elif bill.paid_amount > 0:
            bill.status = 'partial'
        else:
            bill.status = 'unpaid'

        db.session.commit()
        flash('Purchase bill created successfully!', 'success')
        return redirect(url_for('purchase.bill_detail', id=bill.id))
    
    return render_template('purchase/create_bill.html', form=form, products=products, vendors=vendors, currencies=currencies)

@bp.route('/bill/<int:id>')
@login_required
def bill_detail(id):
    bill = PurchaseBill.query.get_or_404(id)
    return render_template('purchase/bill_detail.html', bill=bill)

@bp.route('/bill/<int:id>/pdf')
@login_required
def bill_pdf(id):
    bill = PurchaseBill.query.get_or_404(id)
    company = Company.query.first()
    
    try:
        buffer = generate_professional_pdf('purchase', bill, company)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"PO_{bill.bill_number}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('purchase.bill_detail', id=id))

@bp.route('/bill/<int:id>/pay', methods=['POST'])
@login_required
def pay_bill(id):
    bill = PurchaseBill.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    
    if amount > 0:
        bill.paid_amount += amount
        if bill.paid_amount >= bill.total:
            bill.status = 'paid'
        else:
            bill.status = 'partial'
        
        db.session.commit()
        flash(f'Payment of ${amount} recorded successfully!', 'success')
    
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

@bp.route('/vendors')
@login_required
def vendors():
    vendors = Vendor.query.all()
    return render_template('purchase/vendors.html', vendors=vendors)

@bp.route('/vendor/<int:id>')
@login_required
def vendor_profile(id):
    vendor = Vendor.query.get_or_404(id)
    # Calculated fields already in model
    return render_template('purchase/vendor_profile.html', vendor=vendor)

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
            gst_number=form.gst_number.data
        )
        db.session.add(vendor)
        db.session.commit()
        flash('Vendor added successfully!', 'success')
        return redirect(url_for('purchase.vendors'))
    
    return render_template('purchase/add_vendor.html', form=form)

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