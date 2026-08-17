from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from app.utils import permission_required, log_activity
from app import db
from app.models import (
    Quotation, QuotationItem, Product, Customer, Salesman, Currency,
    Company, InvoiceSettings, Sale, SaleItem, ProductWarehouseStock, Warehouse
)
from app.forms import SaleForm
from datetime import datetime
from app.pdf_utils import generate_professional_pdf

bp = Blueprint('quotation', __name__)


def _format_quotation_number(settings, number):
    """Prefix + plain sequential number, e.g. QTN-7 — no zero-padding."""
    return f"{settings.quotation_prefix or 'QO-'}{number}{settings.quotation_suffix or ''}"


def sellable_products(existing_product_ids=None):
    """Same restriction as the Sales module: only finished-good products,
    plus any product already used on the quotation being edited."""
    products = Product.query.filter_by(is_manufactured=True).all()
    if existing_product_ids:
        have_ids = {p.id for p in products}
        missing_ids = set(existing_product_ids) - have_ids
        if missing_ids:
            products += Product.query.filter(Product.id.in_(missing_ids)).all()
    return products


def _parse_items_from_form():
    """Read the product/warehouse/qty/price/discount/delivery line-item arrays
    posted by the create/edit quotation form — same field-name convention as
    the Sales invoice form. The warehouse tag is informational only (quotations
    never touch stock), but carries through to the Sale on convert-to-sale."""
    product_ids = request.form.getlist('product_id[]')
    warehouses = request.form.getlist('warehouse_id[]')
    quantities = request.form.getlist('quantity[]')
    prices = request.form.getlist('price[]')
    deliveries = request.form.getlist('delivery[]')
    item_discounts = request.form.getlist('discount[]')
    item_unit_discounts = request.form.getlist('unit_discount[]')

    subtotal = 0
    items = []
    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i] and float(quantities[i]) > 0:
            product = Product.query.get(int(product_ids[i]))
            if not product:
                continue
            quantity = float(quantities[i])
            price = float(prices[i])
            delivery_fee = float(deliveries[i]) if i < len(deliveries) and deliveries[i] else 0
            unit_discount = 0
            if i < len(item_unit_discounts) and item_unit_discounts[i]:
                unit_discount = float(item_unit_discounts[i])
            if unit_discount:
                item_discount = unit_discount * quantity
            else:
                item_discount = float(item_discounts[i]) if i < len(item_discounts) and item_discounts[i] else 0
                unit_discount = (item_discount / quantity) if quantity else 0
            item_subtotal = quantity * price
            total = item_subtotal + delivery_fee
            subtotal += total

            warehouse_id = None
            try:
                warehouse_id = int(warehouses[i]) if i < len(warehouses) and warehouses[i] else None
            except (ValueError, TypeError):
                warehouse_id = None

            items.append({
                'product_id': product.id,
                'warehouse_id': warehouse_id,
                'quantity': quantity,
                'unit_price': price,
                'delivery_fee': delivery_fee,
                'unit_discount': unit_discount,
                'discount': item_discount,
                'total': total
            })
    return items, subtotal


@bp.route('/list')
@login_required
def list_quotations():
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    salesman_id = request.args.get('salesman_id', type=int)
    customer_id = request.args.get('customer_id', type=int)
    warehouse_id = request.args.get('warehouse_id', type=int)

    query = Quotation.query

    if status != 'all':
        query = query.filter(Quotation.status == status)

    if salesman_id:
        query = query.filter(Quotation.salesman_id == salesman_id)

    if customer_id:
        query = query.filter(Quotation.customer_id == customer_id)

    if warehouse_id:
        query = query.join(QuotationItem, QuotationItem.quotation_id == Quotation.id).filter(
            QuotationItem.warehouse_id == warehouse_id
        ).distinct()

    if search:
        like = f"%{search}%"
        query = query.join(Customer, Quotation.customer_id == Customer.id, isouter=True).filter(
            db.or_(Quotation.quotation_number.ilike(like), Customer.name.ilike(like))
        )

    if from_date:
        try:
            query = query.filter(Quotation.date >= datetime.strptime(from_date, '%Y-%m-%d'))
        except ValueError:
            pass
    if to_date:
        try:
            query = query.filter(Quotation.date <= datetime.strptime(to_date, '%Y-%m-%d'))
        except ValueError:
            pass

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Quotation.date.desc(), Quotation.id.desc()).paginate(page=page, per_page=25, error_out=False)

    counts = {
        'all': Quotation.query.count(),
        'draft': Quotation.query.filter_by(status='draft').count(),
        'sent': Quotation.query.filter_by(status='sent').count(),
        'accepted': Quotation.query.filter_by(status='accepted').count(),
        'rejected': Quotation.query.filter_by(status='rejected').count(),
        'expired': Quotation.query.filter_by(status='expired').count(),
    }

    salesmen = Salesman.query.filter_by(is_active=True).all()
    customers = Customer.query.order_by(Customer.name).all()
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    company = Company.query.first()
    date_format = company.date_format if company and company.date_format else '%Y-%m-%d'
    return render_template('quotation/quotations.html', quotations=pagination.items, pagination=pagination,
                           status=status, search=search, counts=counts, salesmen=salesmen, customers=customers,
                           warehouses=warehouses, salesman_id=salesman_id, customer_id=customer_id,
                           warehouse_id=warehouse_id,
                           from_date=from_date, to_date=to_date, date_format=date_format)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('quotations', action='add')
def create_quotation():
    form = SaleForm()
    customers = Customer.query.all()
    products = sellable_products()
    currencies = Currency.query.filter_by(is_active=True).all()
    salesmen = Salesman.query.filter_by(is_active=True).all()
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()

    form.customer_id.choices = [(0, 'Walk-in Customer')] + [(c.id, c.name) for c in customers]
    form.salesman_id.choices = [('', 'Select Salesman')] + [(s.id, s.name) for s in salesmen]

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        salesman_id = request.form.get('salesman_id')
        date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')

        quote_items, subtotal = _parse_items_from_form()

        tax_rate = float(request.form.get('tax_rate', 0))
        tax = subtotal * (tax_rate / 100)
        discount = sum(item['discount'] for item in quote_items)
        delivery_charge = float(request.form.get('delivery_charge', 0))
        total = subtotal + tax + delivery_charge - discount

        settings = InvoiceSettings.query.first()
        if not settings:
            settings = InvoiceSettings(quotation_prefix='QO-', quotation_suffix='', quotation_next_number=1)
            db.session.add(settings)
        quotation_number = _format_quotation_number(settings, settings.quotation_next_number or 1)
        settings.quotation_next_number = (settings.quotation_next_number or 1) + 1

        quotation = Quotation(
            quotation_number=quotation_number,
            customer_id=customer_id if customer_id and customer_id != '0' else None,
            salesman_id=salesman_id if salesman_id and salesman_id != '0' else None,
            date=date,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax=tax,
            discount=discount,
            discount_type='fixed',
            delivery_charge=delivery_charge,
            total=total,
            status='draft',
            currency_id=request.form.get('currency_id') or None,
            exchange_rate=float(request.form.get('exchange_rate', 1) or 1),
            notes=request.form.get('notes'),
            terms=request.form.get('terms'),
            created_by=current_user.id,
        )

        due_date_str = request.form.get('due_date')
        if due_date_str:
            try:
                quotation.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                quotation.due_date = None

        db.session.add(quotation)
        db.session.flush()

        for item in quote_items:
            db.session.add(QuotationItem(
                quotation_id=quotation.id,
                product_id=item['product_id'],
                warehouse_id=item.get('warehouse_id'),
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                delivery_fee=item.get('delivery_fee', 0),
                unit_discount=item.get('unit_discount', 0),
                discount=item.get('discount', 0),
                total=item['total']
            ))

        db.session.flush()
        db.session.expire(quotation, ['items'])
        quotation.calculate_totals()

        db.session.commit()

        log_activity('Quotations', f'Created Quotation #{quotation.quotation_number}',
                    f'Customer: {quotation.customer.name if quotation.customer else "Walk-in Customer"}, Total: {quotation.total}')

        flash('Quotation created successfully!', 'success')
        return redirect(url_for('quotation.quotation_detail', id=quotation.id))

    # Preview-only: the real quotation_number is assigned server-side on save
    # (see the POST branch above), so this doesn't touch/increment the counter.
    qn_settings = InvoiceSettings.query.first()
    if qn_settings:
        next_quotation_number = _format_quotation_number(qn_settings, qn_settings.quotation_next_number or 1)
    else:
        next_quotation_number = 'QO-1'

    return render_template('quotation/create_quotation.html', form=form, products=products, customers=customers,
                           currencies=currencies, salesmen=salesmen, warehouses=warehouses, now=datetime.now(),
                           next_quotation_number=next_quotation_number)


@bp.route('/<int:id>')
@login_required
def quotation_detail(id):
    quotation = Quotation.query.get_or_404(id)
    company = Company.query.first()
    date_format = company.date_format if company and company.date_format else '%Y-%m-%d'
    return render_template('quotation/quotation_detail.html', quotation=quotation, date_format=date_format)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('quotations', action='edit')
def edit_quotation(id):
    quotation = Quotation.query.get_or_404(id)
    if quotation.converted_sale_id:
        flash('This quotation has already been converted to a sale and can no longer be edited.', 'warning')
        return redirect(url_for('quotation.quotation_detail', id=id))

    form = SaleForm(obj=quotation)
    customers = Customer.query.all()
    products = sellable_products(existing_product_ids=[item.product_id for item in quotation.items])
    currencies = Currency.query.filter_by(is_active=True).all()
    salesmen = Salesman.query.filter_by(is_active=True).all()
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()

    form.customer_id.choices = [(0, 'Walk-in Customer')] + [(c.id, c.name) for c in customers]
    form.salesman_id.choices = [('', 'Select Salesman')] + [(s.id, s.name) for s in salesmen]

    if request.method == 'POST':
        QuotationItem.query.filter_by(quotation_id=quotation.id).delete()

        customer_id = request.form.get('customer_id')
        salesman_id = request.form.get('salesman_id')
        date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')

        quote_items, subtotal = _parse_items_from_form()

        tax_rate = float(request.form.get('tax_rate', 0))
        tax = subtotal * (tax_rate / 100)
        discount = sum(item['discount'] for item in quote_items)
        delivery_charge = float(request.form.get('delivery_charge', 0))

        quotation.customer_id = customer_id if customer_id and customer_id != '0' else None
        quotation.salesman_id = salesman_id if salesman_id and salesman_id != '0' else None
        quotation.date = date
        quotation.subtotal = subtotal
        quotation.tax_rate = tax_rate
        quotation.tax = tax
        quotation.discount = discount
        quotation.discount_type = 'fixed'
        quotation.delivery_charge = delivery_charge
        quotation.currency_id = request.form.get('currency_id') or None
        quotation.exchange_rate = float(request.form.get('exchange_rate', 1) or 1)
        quotation.notes = request.form.get('notes')
        quotation.terms = request.form.get('terms')
        quotation.updated_at = datetime.utcnow()

        due_date_str = request.form.get('due_date')
        if due_date_str:
            try:
                quotation.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                quotation.due_date = None

        for item in quote_items:
            db.session.add(QuotationItem(
                quotation_id=quotation.id,
                product_id=item['product_id'],
                warehouse_id=item.get('warehouse_id'),
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                delivery_fee=item.get('delivery_fee', 0),
                unit_discount=item.get('unit_discount', 0),
                discount=item.get('discount', 0),
                total=item['total']
            ))

        db.session.flush()
        db.session.expire(quotation, ['items'])
        quotation.calculate_totals()

        db.session.commit()

        log_activity('Quotations', f'Updated Quotation #{quotation.quotation_number}',
                    f'Customer: {quotation.customer.name if quotation.customer else "Walk-in Customer"}, New Total: {quotation.total}')

        flash('Quotation updated successfully!', 'success')
        return redirect(url_for('quotation.quotation_detail', id=quotation.id))

    return render_template('quotation/edit_quotation.html', form=form, quotation=quotation, products=products,
                           customers=customers, currencies=currencies, salesmen=salesmen, warehouses=warehouses, now=datetime.now())


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_quotation(id):
    """Admin-only: quotations can only be deleted by an admin, regardless of
    the granular 'quotations' delete permission other roles may hold."""
    if current_user.role != 'admin':
        flash('Only an admin can delete a quotation.', 'danger')
        return redirect(url_for('quotation.list_quotations'))

    quotation = Quotation.query.get_or_404(id)
    number = quotation.quotation_number
    db.session.delete(quotation)
    db.session.commit()
    log_activity('Quotations', f'Deleted Quotation #{number}')
    flash('Quotation deleted successfully!', 'success')
    return redirect(url_for('quotation.list_quotations'))


@bp.route('/<int:id>/status', methods=['POST'])
@login_required
@permission_required('quotations', action='edit')
def update_quotation_status(id):
    quotation = Quotation.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status not in Quotation.STATUS_LABELS:
        flash('Invalid status.', 'danger')
        return redirect(url_for('quotation.quotation_detail', id=id))

    quotation.status = new_status
    quotation.updated_at = datetime.utcnow()
    db.session.commit()

    log_activity('Quotations', f'Quotation #{quotation.quotation_number} marked {quotation.status_label}')
    flash(f'Quotation marked as {quotation.status_label.title()}.', 'success')
    return redirect(url_for('quotation.quotation_detail', id=id))


@bp.route('/<int:id>/convert', methods=['POST'])
@login_required
@permission_required('quotations', action='edit')
def convert_to_sale(id):
    quotation = Quotation.query.get_or_404(id)

    if quotation.converted_sale_id:
        flash('This quotation has already been converted to a sale.', 'warning')
        return redirect(url_for('quotation.quotation_detail', id=id))

    settings = InvoiceSettings.query.first()
    if not settings:
        settings = InvoiceSettings(invoice_prefix='INV-', invoice_suffix='', next_number=1)
        db.session.add(settings)
    invoice_number = f"{settings.invoice_prefix}{settings.next_number}{settings.invoice_suffix}"
    settings.next_number += 1

    creator_is_admin = (current_user.role == 'admin')

    sale = Sale(
        invoice_number=invoice_number,
        customer_id=quotation.customer_id,
        date=datetime.utcnow(),
        subtotal=quotation.subtotal,
        tax_rate=quotation.tax_rate,
        tax=quotation.tax,
        discount=quotation.discount,
        discount_type=quotation.discount_type,
        delivery_charge=quotation.delivery_charge,
        total=quotation.total,
        status='unpaid',
        currency_id=quotation.currency_id,
        exchange_rate=quotation.exchange_rate,
        salesman_id=quotation.salesman_id,
        notes=quotation.notes,
        terms=quotation.terms,
        created_by=current_user.id,
        is_approved=creator_is_admin,
        approved_by=current_user.id if creator_is_admin else None,
        approved_at=datetime.utcnow() if creator_is_admin else None,
    )
    db.session.add(sale)
    db.session.flush()

    for item in quotation.items:
        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=item.product_id,
            warehouse_id=item.warehouse_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            delivery_fee=item.delivery_fee,
            unit_discount=item.unit_discount,
            discount=item.discount,
            total=item.total
        )
        db.session.add(sale_item)

    if sale.is_approved:
        for item in quotation.items:
            product = Product.query.get(item.product_id)
            if product:
                product.update_quantity(-item.quantity)
                wh_id = item.warehouse_id or product.warehouse_id
                if wh_id:
                    wh_stock = ProductWarehouseStock.query.filter_by(product_id=item.product_id, warehouse_id=wh_id).first()
                    if not wh_stock:
                        wh_stock = ProductWarehouseStock(product_id=item.product_id, warehouse_id=wh_id, quantity=0)
                        db.session.add(wh_stock)
                    wh_stock.quantity -= item.quantity
        sale.stock_updated = True

    db.session.flush()
    db.session.expire(sale, ['items'])
    sale.calculate_totals()
    sale.update_status()

    quotation.converted_sale_id = sale.id
    quotation.status = 'accepted'
    quotation.updated_at = datetime.utcnow()

    db.session.commit()

    log_activity('Quotations', f'Converted Quotation #{quotation.quotation_number} to Invoice #{sale.invoice_number}')
    flash(f'Quotation converted to Invoice #{sale.invoice_number}!', 'success')
    return redirect(url_for('sales.invoice_detail', id=sale.id))


@bp.route('/<int:id>/pdf')
@login_required
def quotation_pdf(id):
    quotation = Quotation.query.get_or_404(id)
    company = Company.query.first()
    settings = InvoiceSettings.query.first()

    try:
        buffer = generate_professional_pdf('quotation', quotation, company, settings)
        response = make_response(buffer)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="quotation_{quotation.quotation_number or "unknown"}.pdf"'
        return response
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('quotation.quotation_detail', id=id))


@bp.route('/<int:id>/pdf/view')
@login_required
def quotation_pdf_view(id):
    quotation = Quotation.query.get_or_404(id)
    company = Company.query.first()
    settings = InvoiceSettings.query.first()

    try:
        buffer = generate_professional_pdf('quotation', quotation, company, settings)
        response = make_response(buffer)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="{quotation.quotation_number}.pdf"'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('quotation.quotation_detail', id=id))


@bp.route('/public/<token>')
def public_quotation(token):
    """Public (customer-facing, token-based) Quotation PDF — the link shared to
    a customer over WhatsApp. No login required."""
    quotation = Quotation.query.filter_by(access_token=token).first_or_404()

    if quotation.token_expiry and quotation.token_expiry < datetime.utcnow():
        return "Link expired", 403

    company = Company.query.first()
    settings = InvoiceSettings.query.first()

    try:
        buffer = generate_professional_pdf('quotation', quotation, company, settings)
        response = make_response(buffer)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="quotation_{quotation.quotation_number or "unknown"}.pdf"'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        return f"Error generating PDF: {str(e)}", 500
