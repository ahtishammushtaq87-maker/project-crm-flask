from flask import Blueprint, render_template, request, send_file, jsonify, flash, redirect, url_for
from app.utils import permission_required
from flask_login import login_required
from app import db
from app.models import Sale, SaleItem, PurchaseBill, PurchaseItem, Product, Vendor, Customer, Company, Expense, ExpenseCategory, SaleReturn, SaleReturnItem, BOM, BOMItem, BOMVersion, ManufacturingOrder, Staff, SalaryPayment, SalaryAdvance, Warehouse, Attendance, ProductCategory
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
import pandas as pd
from io import BytesIO
from app.report_utils import generate_excel, generate_csv, generate_pdf
from app.routes.filters import apply_saved_filter_to_query

bp = Blueprint('reports', __name__)

def get_company_info():
    """Get company information for reports"""
    company = Company.query.first()
    if company:
        return {
            'name': company.name,
            'address': company.address,
            'phone': company.phone,
            'email': company.email
        }
    return {'name': 'ERP Portal', 'address': '', 'phone': '', 'email': ''}

@bp.route('/sales-report')
@login_required
def sales_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    customer_id = request.args.get('customer_id')
    
    # Build query
    query = Sale.query
    
    if start_date:
        query = query.filter(Sale.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Sale.date <= datetime.strptime(end_date, '%Y-%m-%d'))
    if status != 'all':
        query = query.filter(Sale.status == status)
    if search:
        query = query.filter(Sale.invoice_number.ilike(f'%{search}%'))
    if customer_id and customer_id != 'all':
        query = query.filter(Sale.customer_id == customer_id)
        
    query = apply_saved_filter_to_query(query, 'sales_report', request.args)
    
    sales = query.order_by(Sale.date.desc()).all()
    
    # Calculate totals
    total_sales = sum(s.total for s in sales)
    total_paid = sum(s.paid_amount for s in sales)
    total_balance = sum(s.balance_due for s in sales)
    total_count = len(sales)
    
    customers = Customer.query.order_by(Customer.name).all()
    
    return render_template('reports/sales_report.html',
                         sales=sales,
                         total_sales=total_sales,
                         total_paid=total_paid,
                         total_balance=total_balance,
                         total_count=total_count,
                         start_date=start_date,
                         end_date=end_date,
                         status=status,
                         search=search,
                         customers=customers,
                         current_customer_id=customer_id,
                         active_module='sales_report',
                         filter_id=request.args.get('filter_id'))

@bp.route('/purchase-report')
@login_required
def purchase_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    vendor_id = request.args.get('vendor_id')
    
    query = PurchaseBill.query
    
    if start_date:
        query = query.filter(PurchaseBill.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(PurchaseBill.date <= datetime.strptime(end_date, '%Y-%m-%d'))
    if status != 'all':
        query = query.filter(PurchaseBill.status == status)
    if search:
        query = query.filter(PurchaseBill.bill_number.ilike(f'%{search}%'))
    if vendor_id and vendor_id != 'all':
        query = query.filter(PurchaseBill.vendor_id == vendor_id)
    
    query = apply_saved_filter_to_query(query, 'purchase_report', request.args)
    
    purchases = query.order_by(PurchaseBill.date.desc()).all()
    
    total_purchases = sum(p.total for p in purchases)
    total_paid = sum(p.paid_amount for p in purchases)
    total_balance = sum(p.balance_due for p in purchases)
    total_count = len(purchases)
    
    vendors = Vendor.query.order_by(Vendor.name).all()
    
    return render_template('reports/purchase_report.html',
                         purchases=purchases,
                         total_purchases=total_purchases,
                         total_paid=total_paid,
                         total_balance=total_balance,
                         total_count=total_count,
                         start_date=start_date,
                         end_date=end_date,
                         status=status,
                         search=search,
                         vendors=vendors,
                         current_vendor_id=vendor_id,
                         active_module='purchase_report',
                         filter_id=request.args.get('filter_id'))

@bp.route('/inventory-report')
@login_required
def inventory_report():
    category = request.args.get('category', 'all')
    warehouse_id = request.args.get('warehouse_id', '')
    search = request.args.get('search', '')
    stock_filter = request.args.get('stock_filter', 'all')
    
    query = Product.query
    
    if category != 'all':
        query = query.filter(Product.category.has(name=category))
    if warehouse_id and warehouse_id.isdigit():
        query = query.filter(Product.warehouse_id == int(warehouse_id))
    if search:
        query = query.filter(or_(Product.name.ilike(f'%{search}%'), Product.sku.ilike(f'%{search}%')))
    
    if stock_filter == 'min':
        query = query.filter(Product.quantity <= Product.min_quantity)
    elif stock_filter == 'high':
        query = query.filter(Product.quantity >= Product.max_quantity)
    
    query = apply_saved_filter_to_query(query, 'inventory_report', request.args)
    
    products = query.order_by(Product.name).all()
    
    # Get categories for filter
    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    categories = [c.name for c in categories if c.name]
    
    # Get warehouses for filter
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    
    total_value = sum(p.stock_value for p in products)
    total_items = sum(p.quantity for p in products)
    
    return render_template('reports/inventory_report.html',
                         products=products,
                         categories=categories,
                         warehouses=warehouses,
                         current_category=category,
                         current_warehouse_id=warehouse_id,
                         search=search,
                         stock_filter=stock_filter,
                         total_value=total_value,
                         total_items=total_items,
                         active_module='inventory_report',
                         filter_id=request.args.get('filter_id'))


@bp.route('/inventory-details-report')
@login_required
def inventory_details_report():
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    warehouse_id = request.args.get('warehouse_id', '')
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    
    query = Product.query
    
    if category != 'all':
        query = query.filter(Product.category.has(name=category))
    if warehouse_id and warehouse_id.isdigit():
        query = query.filter(Product.warehouse_id == int(warehouse_id))
    if search:
        query = query.filter(or_(Product.name.ilike(f'%{search}%'), Product.sku.ilike(f'%{search}%')))
    
    products = query.order_by(Product.name).all()
    
    product_movements = []
    
    # Get sales and purchases in date range for each product
    for product in products:
        sold_qty = 0
        purchased_qty = 0
        
        # Sales
        sale_items = SaleItem.query.join(Sale).filter(
            SaleItem.product_id == product.id
        ).all()
        for item in sale_items:
            if from_date:
                sale_date = item.sale.date if item.sale else None
                if sale_date and sale_date >= datetime.strptime(from_date, '%Y-%m-%d'):
                    if to_date:
                        if sale_date <= datetime.strptime(to_date, '%Y-%m-%d'):
                            sold_qty += item.quantity
                    else:
                        sold_qty += item.quantity
            else:
                sold_qty += item.quantity
        
        # Purchases
        purchase_items = PurchaseItem.query.join(PurchaseBill).filter(
            PurchaseItem.product_id == product.id
        ).all()
        for item in purchase_items:
            if from_date:
                purchase_date = item.bill.date if item.bill else None
                if purchase_date and purchase_date >= datetime.strptime(from_date, '%Y-%m-%d'):
                    if to_date:
                        if purchase_date <= datetime.strptime(to_date, '%Y-%m-%d'):
                            purchased_qty += item.quantity
                    else:
                        purchased_qty += item.quantity
            else:
                purchased_qty += item.quantity
        
        product_movements.append({
            'product': product,
            'sold': sold_qty,
            'purchased': purchased_qty,
            'current_stock': product.quantity,
            'warehouse': product.warehouse.name if product.warehouse else 'No Warehouse'
        })
    
    # Get warehouses for filter
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    
    # Get categories for filter
    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    categories = [c.name for c in categories if c.name]
    
    return render_template('reports/inventory_details_report.html',
                         product_movements=product_movements,
                         warehouses=warehouses,
                         categories=categories,
                         from_date=from_date,
                         to_date=to_date,
                         current_warehouse_id=warehouse_id,
                         current_category=category,
                         search=search)


@bp.route('/cogs-report')
@login_required
def cogs_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')

    query = SaleItem.query.join(Sale).join(Product)
    if start_date:
        query = query.filter(Sale.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Sale.date <= datetime.strptime(end_date, '%Y-%m-%d'))
    if category != 'all':
        query = query.join(Product.category).filter(ProductCategory.name == category)
    if search:
        query = query.filter(or_(Product.name.ilike(f'%{search}%'), Product.sku.ilike(f'%{search}%')))

    query = apply_saved_filter_to_query(query, 'cogs_report', request.args)

    sale_items = query.order_by(Sale.date.desc()).all()

    product_stats = {}
    total_cogs = 0
    total_revenue = 0
    total_quantity = 0

    for item in sale_items:
        prod = item.product
        if not prod:
            continue

        cogs = (prod.cost_price or 0) * item.quantity
        revenue = item.total

        if prod.id not in product_stats:
            product_stats[prod.id] = {
                'product_name': prod.name,
                'sku': prod.sku,
                'category': prod.category.name if prod.category else 'Uncategorized',
                'cost_price': prod.cost_price or 0,
                'quantity_sold': 0,
                'cogs': 0,
                'revenue': 0,
                'profit': 0
            }

        product_stats[prod.id]['quantity_sold'] += item.quantity
        product_stats[prod.id]['cogs'] += cogs
        product_stats[prod.id]['revenue'] += revenue
        product_stats[prod.id]['profit'] = product_stats[prod.id]['revenue'] - product_stats[prod.id]['cogs']

        total_cogs += cogs
        total_revenue += revenue
        total_quantity += item.quantity

    products = sorted(product_stats.values(), key=lambda x: x['product_name'])
    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    categories = [c.name for c in categories if c.name]

    return render_template('reports/cogs_report.html',
                          products=products,
                          categories=categories,
                          current_category=category,
                          start_date=start_date,
                          end_date=end_date,
                          search=search,
                          total_cogs=total_cogs,
                          total_revenue=total_revenue,
                          total_quantity=total_quantity,
                          total_profit=total_revenue - total_cogs,
                          active_module='cogs_report',
                          filter_id=request.args.get('filter_id'))

@bp.route('/expense-report')
@login_required
def expense_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search', '')
    category_id = request.args.get('category_id')
    vendor_id = request.args.get('vendor_id')
    
    query = Expense.query
    
    if start_date:
        query = query.filter(Expense.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Expense.date <= datetime.strptime(end_date, '%Y-%m-%d'))
    if search:
        query = query.filter(or_(Expense.expense_number.ilike(f'%{search}%'), Expense.description.ilike(f'%{search}%')))
    if category_id and category_id != 'all':
        query = query.filter(Expense.category_id == category_id)
    if vendor_id and vendor_id != 'all':
        query = query.filter(Expense.vendor_id == vendor_id)
    
    query = query.filter(Expense.status == 'confirmed')
        
    query = apply_saved_filter_to_query(query, 'expense_report', request.args)
    
    expenses = query.order_by(Expense.date.desc()).all()
    
    # Unified Expenses (Regular + Payroll)
    unified_expenses = []
    # Add regular expenses
    for e in expenses:
        unified_expenses.append({
            'date': e.date,
            'number': e.expense_number,
            'category': e.expense_category.name if e.expense_category else 'Other',
            'vendor': e.vendor.name if e.vendor else 'N/A',
            'description': e.description,
            'method': e.payment_method,
            'amount': e.amount,
            'type': 'Expense'
        })
    
    # Add payroll only if no category/vendor filters are active (unless payroll-specific)
    if (not category_id or category_id == 'all') and (not vendor_id or vendor_id == 'all'):
        # Add Salary Payments
        pay_query = SalaryPayment.query.join(Staff).filter(SalaryPayment.status == 'paid')
        if start_date: pay_query = pay_query.filter(SalaryPayment.payment_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date: pay_query = pay_query.filter(SalaryPayment.payment_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        if search: pay_query = pay_query.filter(Staff.name.ilike(f'%{search}%'))
        
        for p in pay_query.all():
            unified_expenses.append({
                'date': p.payment_date,
                'number': f"PAY-{p.id}",
                'category': 'Payroll',
                'vendor': p.staff.name,
                'description': f"Salary for {p.month}/{p.year}",
                'method': p.payment_method,
                'amount': p.net_salary,
                'type': 'Salary'
            })
            
        # Add Salary Advances
        adv_query = SalaryAdvance.query.join(Staff)
        if start_date: adv_query = adv_query.filter(SalaryAdvance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date: adv_query = adv_query.filter(SalaryAdvance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        if search: adv_query = adv_query.filter(Staff.name.ilike(f'%{search}%'))
        
        for a in adv_query.all():
            unified_expenses.append({
                'date': a.date,
                'number': f"ADV-{a.id}",
                'category': 'Payroll Advance',
                'vendor': a.staff.name,
                'description': a.description or "Staff Advance",
                'method': 'Cash', # Assuming cash for advances as per generic practice
                'amount': a.amount,
                'type': 'Advance'
            })
            
    # Re-sort unified list by date descending (normalize to date for comparison)
    unified_expenses.sort(key=lambda x: x['date'].date() if hasattr(x['date'], 'date') else x['date'], reverse=True)
    
    total_expenses = sum(e['amount'] for e in unified_expenses)
    total_count = len(unified_expenses)
    
    categories = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    vendors = Vendor.query.order_by(Vendor.name).all()
    
    return render_template('reports/expense_report.html',
                         expenses=unified_expenses,
                         total_expenses=total_expenses,
                         total_count=total_count,
                         start_date=start_date,
                         end_date=end_date,
                         search=search,
                         categories=categories,
                         vendors=vendors,
                         current_category_id=category_id,
                         current_vendor_id=vendor_id,
                         active_module='expense_report',
                         filter_id=request.args.get('filter_id'))

@bp.route('/return-report')
@login_required
def return_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    customer_id = request.args.get('customer_id')

    query = SaleReturn.query

    if start_date:
        query = query.filter(SaleReturn.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(SaleReturn.date <= datetime.strptime(end_date, '%Y-%m-%d'))
    if status != 'all':
        query = query.filter(SaleReturn.status == status)
    if search:
        query = query.filter(SaleReturn.return_number.ilike(f'%{search}%'))
    if customer_id and customer_id != 'all':
        query = query.filter(SaleReturn.customer_id == int(customer_id))

    query = apply_saved_filter_to_query(query, 'return_report', request.args)

    returns = query.order_by(SaleReturn.date.desc()).all()

    total_returns = sum(r.total for r in returns)
    total_count = len(returns)

    customers = Customer.query.order_by(Customer.name).all()

    return render_template('reports/return_report.html',
                           returns=returns,
                           total_returns=total_returns,
                           total_count=total_count,
                           start_date=start_date,
                           end_date=end_date,
                           status=status,
                           search=search,
                           customers=customers,
                           current_customer_id=customer_id,
                           active_module='return_report',
                           filter_id=request.args.get('filter_id'))


@bp.route('/vendor-report')
@login_required
def vendor_report():
    search = request.args.get('search', '')
    
    query = Vendor.query
    if search:
        query = query.filter(or_(Vendor.name.ilike(f'%{search}%'), Vendor.gst_number.ilike(f'%{search}%')))
        
    query = apply_saved_filter_to_query(query, 'vendor_report', request.args)
    
    vendors = query.order_by(Vendor.name).all()
    
    total_purchases = sum(v.total_purchases for v in vendors)
    total_outstanding = sum(v.outstanding_balance for v in vendors)
    
    return render_template('reports/vendor_report.html',
                         vendors=vendors,
                         search=search,
                         total_purchases=total_purchases,
                         total_outstanding=total_outstanding,
                         active_module='vendor_report',
                         filter_id=request.args.get('filter_id'))

@bp.route('/customer-report')
@login_required
def customer_report():
    search = request.args.get('search', '')
    
    query = Customer.query
    if search:
        query = query.filter(or_(Customer.name.ilike(f'%{search}%'), Customer.gst_number.ilike(f'%{search}%')))
        
    query = apply_saved_filter_to_query(query, 'customer_report', request.args)
    
    customers = query.order_by(Customer.name).all()
    
    total_sales = sum(c.total_sales for c in customers)
    total_outstanding = sum(c.outstanding_balance for c in customers)
    
    return render_template('reports/customer_report.html',
                         customers=customers,
                         search=search,
                         total_sales=total_sales,
                         total_outstanding=total_outstanding,
                         active_module='customer_report',
                         filter_id=request.args.get('filter_id'))

@bp.route('/manufacturing-report')
@login_required
def manufacturing_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status', 'all')
    product_id = request.args.get('product_id')
    
    query = ManufacturingOrder.query.join(BOM)
    
    if start_date:
        query = query.filter(ManufacturingOrder.start_date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(ManufacturingOrder.start_date <= datetime.strptime(end_date, '%Y-%m-%d'))
    if status != 'all':
        query = query.filter(ManufacturingOrder.status == status)
    if product_id and product_id != 'all':
        query = query.filter(BOM.product_id == int(product_id))
        
    query = apply_saved_filter_to_query(query, 'manufacturing_report', request.args)
    
    orders = query.order_by(ManufacturingOrder.start_date.desc()).all()
    
    # Calculate stats
    total_qty = sum(o.quantity_to_produce for o in orders)
    total_cost = sum(o.total_cost for o in orders)
    total_material = sum(o.actual_material_cost or 0 for o in orders)
    total_labor = sum(o.actual_labor_cost or 0 for o in orders)
    total_count = len(orders)
    
    products = Product.query.filter(Product.id.in_(db.session.query(BOM.product_id).distinct())).all()
    
    return render_template('reports/manufacturing_report.html',
                         orders=orders,
                         total_qty=total_qty,
                         total_cost=total_cost,
                         total_material=total_material,
                         total_labor=total_labor,
                         total_count=total_count,
                         start_date=start_date,
                         end_date=end_date,
                         status=status,
                         products=products,
                         current_product_id=product_id,
                         active_module='manufacturing_report',
                         filter_id=request.args.get('filter_id'))

@bp.route('/bom-report')
@login_required
def bom_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    product_id = request.args.get('product_id')
    version_filter = request.args.get('version', 'all')
    view_mode = request.args.get('view_mode', 'boms')
    
    # Get BOMs
    query = BOM.query
    
    if start_date:
        query = query.filter(BOM.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(BOM.created_at <= datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
    if product_id and product_id != 'all':
        query = query.filter(BOM.product_id == int(product_id))
    if version_filter != 'all':
        if version_filter == 'active':
            query = query.filter(BOM.is_active == True)
        else:
            query = query.filter(BOM.is_active == False)
    
    query = apply_saved_filter_to_query(query, 'bom_report', request.args)
    
    boms = query.order_by(BOM.created_at.desc()).all()
    
    # Get BOM versions for all filtered BOMs
    bom_ids = [b.id for b in boms]
    all_versions = []
    if bom_ids:
        version_query = BOMVersion.query.filter(BOMVersion.bom_id.in_(bom_ids))
        if start_date:
            version_query = version_query.filter(BOMVersion.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            version_query = version_query.filter(BOMVersion.created_at <= datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        all_versions = version_query.order_by(BOMVersion.created_at.desc()).all()
    
    total_count = len(boms)
    total_cost = sum(b.total_cost for b in boms)
    total_versions = len(all_versions)
    
    products = Product.query.order_by(Product.name).all()
    
    return render_template('reports/bom_report.html',
                         boms=boms,
                         all_versions=all_versions,
                         total_count=total_count,
                         total_cost=total_cost,
                         total_versions=total_versions,
                         start_date=start_date,
                         end_date=end_date,
                         products=products,
                         current_product_id=product_id,
                         version_filter=version_filter,
                         view_mode=view_mode,
                         active_module='bom_report',
                         filter_id=request.args.get('filter_id'))

@bp.route('/salary-report')
@login_required
def salary_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    staff_id = request.args.get('staff_id')
    
    query = SalaryPayment.query
    
    if start_date:
        query = query.filter(SalaryPayment.payment_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(SalaryPayment.payment_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    if staff_id and staff_id != 'all':
        query = query.filter(SalaryPayment.staff_id == int(staff_id))
    
    query = apply_saved_filter_to_query(query, 'salary_report', request.args)
        
    payments = query.order_by(SalaryPayment.payment_date.desc()).all()
    
    total_base = sum(p.base_salary for p in payments)
    total_bonus = sum(p.bonus for p in payments)
    total_deductions = sum(p.advance_deduction + p.other_deductions for p in payments)
    total_net = sum(p.net_salary for p in payments)
    total_count = len(payments)
    
    all_staff = Staff.query.order_by(Staff.name).all()
    
    return render_template('reports/salary_report.html',
                         payments=payments,
                         total_base=total_base,
                         total_bonus=total_bonus,
                         total_deductions=total_deductions,
                         total_net=total_net,
                         total_count=total_count,
                         start_date=start_date,
                         end_date=end_date,
                         all_staff=all_staff,
                         current_staff_id=staff_id,
                         active_module='salary_report',
                         filter_id=request.args.get('filter_id'))

@bp.route('/profit-loss')
@login_required
def profit_loss_report():
    """Comprehensive Profit and Loss Report"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        # Default to first day of current month
        now = datetime.now()
        start_date = datetime(now.year, now.month, 1)
        start_date_str = start_date.strftime('%Y-%m-%d')
        
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        # Default to today
        end_date = datetime.now()
        end_date_str = end_date.strftime('%Y-%m-%d')
    
    # 1. RevenueSection
    sales = Sale.query.filter(Sale.date >= start_date, Sale.date <= end_date).all()
    returns = SaleReturn.query.filter(SaleReturn.date >= start_date, SaleReturn.date <= end_date).all()
    
    total_revenue = sum(s.total for s in sales)
    total_returns = sum(r.total for r in returns)
    net_revenue = total_revenue - total_returns
    
    # 2. COGS Section: Sum(SaleItem.qty * Product.cost_price)
    sale_items = SaleItem.query.join(Sale).filter(Sale.date >= start_date, Sale.date <= end_date).all()
    total_cogs = sum((item.product.cost_price or 0) * item.quantity for item in sale_items)
    
    # 3. Gross Profit
    gross_profit = net_revenue - total_cogs
    
    # 4. Operating Expenses (Deducted from Profit)
    # Categorized Expenses - EXCLUDING BOM overheads as they are informational/inventory related
    operating_expenses = Expense.query.filter(
        Expense.date >= start_date, 
        Expense.date <= end_date,
        Expense.is_bom_overhead == False,
        Expense.status == 'confirmed'
    ).all()
    
    expense_summary = {}
    divided_expense_summary = {}
    for e in operating_expenses:
        cat_name = e.expense_category.name if e.expense_category else 'Other'
        if e.is_monthly_divided:
            if e.monthly_start_date and e.monthly_end_date:
                exp_start = datetime.combine(e.monthly_start_date, datetime.min.time())
                exp_end = datetime.combine(e.monthly_end_date, datetime.min.time())
                period_start = max(start_date, exp_start)
                period_end = min(end_date, exp_end)
                if period_end >= period_start:
                    total_days = (e.monthly_end_date - e.monthly_start_date).days + 1
                    active_days = (period_end.date() - period_start.date()).days + 1
                    if total_days > 0:
                        daily_amount = e.amount / total_days
                        pro_rata_amount = daily_amount * active_days
                        divided_expense_summary[cat_name] = divided_expense_summary.get(cat_name, 0) + pro_rata_amount
            else:
                divided_expense_summary[cat_name] = divided_expense_summary.get(cat_name, 0) + e.amount
        else:
            expense_summary[cat_name] = expense_summary.get(cat_name, 0) + e.amount
    
    total_divided_expenses = sum(divided_expense_summary.values())
    
    # Calculate Daily Payroll (same as Dashboard) - Active staff daily salary × days in period
    from calendar import monthrange
    from datetime import timedelta
    
    # Get attendance records for the period
    attendance_records_by_date = {}
    attendance_records = Attendance.query.filter(
        Attendance.date >= start_date.date(),
        Attendance.date <= end_date.date()
    ).all()
    for record in attendance_records:
        if record.date not in attendance_records_by_date:
            attendance_records_by_date[record.date] = []
        attendance_records_by_date[record.date].append(record)
    
    attendance_payroll = sum(record.earned_amount for record in attendance_records)
    
    # Active staff daily salary for days without attendance
    active_staff = Staff.query.filter_by(is_active=True).all()
    period_start = start_date.date()
    period_end = end_date.date()
    daily_payroll_for_period = attendance_payroll
    
    for staff in active_staff:
        if period_start.month == period_end.month and period_start.year == period_end.year:
            days_in_period = (period_end - period_start).days + 1
            _, days_in_month = monthrange(period_start.year, period_start.month)
            daily_rate = staff.monthly_salary / float(days_in_month)
            days_without_attendance = 0
            current_date = period_start
            while current_date <= period_end:
                if current_date not in attendance_records_by_date:
                    days_without_attendance += 1
                current_date += timedelta(days=1)
            daily_payroll_for_period += daily_rate * days_without_attendance
        else:
            current_date = period_start
            while current_date <= period_end:
                _, days_in_month = monthrange(current_date.year, current_date.month)
                month_end = datetime(current_date.year, current_date.month, days_in_month).date()
                actual_end = min(month_end, period_end)
                daily_rate = staff.monthly_salary / float(days_in_month)
                days_without_attendance = 0
                check_date = current_date
                while check_date <= actual_end:
                    if check_date not in attendance_records_by_date:
                        days_without_attendance += 1
                    check_date += timedelta(days=1)
                daily_payroll_for_period += daily_rate * days_without_attendance
                if actual_end == month_end:
                    current_date = datetime(
                        current_date.year if current_date.month < 12 else current_date.year + 1,
                        (current_date.month % 12) + 1,
                        1
                    ).date()
                else:
                    break
    
    total_payroll = daily_payroll_for_period
    
    # Calculate Total Operating Expenses
    total_operating_expenses = sum(expense_summary.values()) + total_divided_expenses + total_payroll
    net_profit = gross_profit - total_operating_expenses
    
    # 5. Inventory & Manufacturing Activity (Displayed but NOT deducted from Net Profit)
    # Direct Purchases
    purchases = PurchaseBill.query.filter(PurchaseBill.date >= start_date, PurchaseBill.date <= end_date).all()
    total_purchases = sum(p.total for p in purchases)
    
    # BOM/Manufacturing Costs (Total actual cost of completed orders)
    manufacturing_orders = ManufacturingOrder.query.filter(
        ManufacturingOrder.status == 'Completed',
        ManufacturingOrder.end_date >= start_date.date(),
        ManufacturingOrder.end_date <= end_date.date()
    ).all()
    total_bom_costs = sum(o.total_cost for o in manufacturing_orders)
    
    # Include BOM overhead expenses that were excluded from operating list
    bom_overhead_expenses = Expense.query.filter(
        Expense.date >= start_date, 
        Expense.date <= end_date,
        Expense.is_bom_overhead == True,
        Expense.status == 'confirmed'
    ).all()
    total_bom_overhead = sum(e.amount for e in bom_overhead_expenses)
    
    total_informational_outflow = total_purchases + total_bom_costs + total_bom_overhead
    
    return render_template('reports/profit_loss.html',
                          start_date=start_date_str,
                          end_date=end_date_str,
                          sales=sales,
                          returns=returns,
                          total_revenue=total_revenue,
                          total_returns=total_returns,
                          net_revenue=net_revenue,
                          total_cogs=total_cogs,
                          gross_profit=gross_profit,
                          expense_categories=expense_summary,
                          divided_expense_categories=divided_expense_summary,
                          total_divided_expenses=total_divided_expenses,
                          total_payroll=total_payroll,
                          purchases=purchases,
                          total_purchases=total_purchases,
                          manufacturing_orders=manufacturing_orders,
                          total_bom_costs=total_bom_costs + total_bom_overhead,
                          total_expenses=total_operating_expenses,
                          total_informational=total_informational_outflow,
                          net_profit=net_profit,
                          active_module='profit_loss_report',
                          filter_id=request.args.get('filter_id'))

@bp.route('/download-report/<string:format>/<string:report_type>')
@login_required
def download_report(format, report_type):
    # Extract common filters from query parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    
    data = []
    headers = []
    title = ""
    
    if report_type == 'sales':
        query = Sale.query
        if start_date: query = query.filter(Sale.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date: query = query.filter(Sale.date <= datetime.strptime(end_date, '%Y-%m-%d'))
        if status != 'all': query = query.filter(Sale.status == status)
        if search: query = query.filter(Sale.invoice_number.ilike(f'%{search}%'))
        
        sales = query.order_by(Sale.date.desc()).all()
        title = "Sales Report"
        headers = ['Invoice Number', 'Date', 'Customer', 'Total', 'Paid', 'Balance', 'Status']
        data = [{
            'Invoice Number': s.invoice_number,
            'Date': s.date.strftime('%Y-%m-%d'),
            'Customer': s.customer.name if s.customer else 'Walk-in',
            'Total': f"{s.total:.2f}",
            'Paid': f"{s.paid_amount:.2f}",
            'Balance': f"{s.balance_due:.2f}",
            'Status': s.status.capitalize()
        } for s in sales]

    elif report_type == 'purchase':
        query = PurchaseBill.query
        if start_date: query = query.filter(PurchaseBill.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date: query = query.filter(PurchaseBill.date <= datetime.strptime(end_date, '%Y-%m-%d'))
        if status != 'all': query = query.filter(PurchaseBill.status == status)
        if search: query = query.filter(PurchaseBill.bill_number.ilike(f'%{search}%'))
        
        purchases = query.order_by(PurchaseBill.date.desc()).all()
        title = "Purchase Report"
        headers = ['Bill Number', 'Date', 'Vendor', 'Total', 'Paid', 'Balance', 'Status']
        data = [{
            'Bill Number': p.bill_number,
            'Date': p.date.strftime('%Y-%m-%d'),
            'Vendor': p.vendor.name if p.vendor else 'Unknown',
            'Total': f"{p.total:.2f}",
            'Paid': f"{p.paid_amount:.2f}",
            'Balance': f"{p.balance_due:.2f}",
            'Status': p.status.capitalize()
        } for p in purchases]

    elif report_type == 'inventory':
        category = request.args.get('category', 'all')
        stock_filter = request.args.get('stock_filter', 'all')
        query = Product.query
        if category != 'all': query = query.filter(Product.category.has(name=category))
        if search: query = query.filter(or_(Product.name.ilike(f'%{search}%'), Product.sku.ilike(f'%{search}%')))
        if stock_filter == 'min': query = query.filter(Product.quantity <= Product.min_quantity)
        elif stock_filter == 'high': query = query.filter(Product.quantity >= Product.max_quantity)
        
        products = query.order_by(Product.name).all()
        title = "Inventory Report"
        headers = ['SKU', 'Product', 'Category', 'Quantity', 'Cost Price', 'Sale Price', 'Stock Value']
        data = [{
            'SKU': p.sku,
            'Product': p.name,
            'Category': p.category.name if p.category else '-',
            'Quantity': p.quantity,
            'Cost Price': f"{p.cost_price:.2f}",
            'Sale Price': f"{p.unit_price:.2f}",
            'Stock Value': f"{p.stock_value:.2f}"
        } for p in products]

    elif report_type == 'cogs':
        category = request.args.get('category', 'all')
        search = request.args.get('search', '')
        query = SaleItem.query.join(Sale).join(Product)
        if start_date: query = query.filter(Sale.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date: query = query.filter(Sale.date <= datetime.strptime(end_date, '%Y-%m-%d'))
        if category != 'all': query = query.join(Product.category).filter(ProductCategory.name == category)
        if search: query = query.filter(or_(Product.name.ilike(f'%{search}%'), Product.sku.ilike(f'%{search}%')))
        
        sale_items = query.order_by(Sale.date.desc()).all()
        product_stats = {}
        for item in sale_items:
            prod = item.product
            if not prod:
                continue
            cogs = (prod.cost_price or 0) * item.quantity
            revenue = item.total
            if prod.id not in product_stats:
                product_stats[prod.id] = {
                    'Product': prod.name,
                    'SKU': prod.sku,
                    'Category': prod.category.name if prod.category else 'Uncategorized',
                    'Qty Sold': 0,
                    'Cost Price': f"{prod.cost_price or 0:.2f}",
                    'COGS': 0,
                    'Revenue': 0,
                    'Profit': 0
                }
            product_stats[prod.id]['Qty Sold'] += item.quantity
            product_stats[prod.id]['COGS'] = float(product_stats[prod.id]['COGS']) + cogs if isinstance(product_stats[prod.id]['COGS'], (int, float)) else cogs
            product_stats[prod.id]['Revenue'] = float(product_stats[prod.id]['Revenue']) + revenue if isinstance(product_stats[prod.id]['Revenue'], (int, float)) else revenue
            product_stats[prod.id]['Profit'] = float(product_stats[prod.id]['Profit']) + (revenue - cogs) if isinstance(product_stats[prod.id]['Profit'], (int, float)) else (revenue - cogs)
        
        products = sorted(product_stats.values(), key=lambda x: x['Product'])
        title = "COGS Report"
        headers = ['Product', 'SKU', 'Category', 'Qty Sold', 'Cost Price', 'COGS', 'Revenue', 'Profit']
        data = [{
            'Product': p['Product'],
            'SKU': p['SKU'],
            'Category': p['Category'],
            'Qty Sold': p['Qty Sold'],
            'Cost Price': p['Cost Price'],
            'COGS': f"{p['COGS']:.2f}",
            'Revenue': f"{p['Revenue']:.2f}",
            'Profit': f"{p['Profit']:.2f}"
        } for p in products]

    elif report_type == 'expense':
        category_id = request.args.get('category_id')
        vendor_id = request.args.get('vendor_id')
        query = Expense.query
        if start_date: query = query.filter(Expense.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date: query = query.filter(Expense.date <= datetime.strptime(end_date, '%Y-%m-%d'))
        if search: query = query.filter(or_(Expense.expense_number.ilike(f'%{search}%'), Expense.description.ilike(f'%{search}%')))
        if category_id and category_id != 'all': query = query.filter(Expense.category_id == category_id)
        if vendor_id and vendor_id != 'all': query = query.filter(Expense.vendor_id == vendor_id)

        expenses = query.order_by(Expense.date.desc()).all()
        
        # Unified list logic reproduced for download
        unified_data = []
        for e in expenses:
            unified_data.append({
                'Expense Number': e.expense_number,
                'Date': e.date.strftime('%Y-%m-%d'),
                'Category': e.expense_category.name if e.expense_category else 'Other',
                'Vendor/Staff': e.vendor.name if e.vendor else 'N/A',
                'Description': e.description,
                'Amount': f"{e.amount:.2f}",
                'Method': e.payment_method
            })
            
        if (not category_id or category_id == 'all') and (not vendor_id or vendor_id == 'all'):
            # Salary Payments
            pay_query = SalaryPayment.query.join(Staff).filter(SalaryPayment.status == 'paid')
            if start_date: pay_query = pay_query.filter(SalaryPayment.payment_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
            if end_date: pay_query = pay_query.filter(SalaryPayment.payment_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
            if search: pay_query = pay_query.filter(Staff.name.ilike(f'%{search}%'))
            
            for p in pay_query.all():
                unified_data.append({
                    'Expense Number': f"PAY-{p.id}",
                    'Date': p.payment_date.strftime('%Y-%m-%d'),
                    'sort_date': p.payment_date,
                    'Category': 'Payroll',
                    'Vendor/Staff': p.staff.name,
                    'Description': f"Salary for {p.month}/{p.year}",
                    'Amount': f"{p.net_salary:.2f}",
                    'Method': p.payment_method
                })
            # Advances
            adv_query = SalaryAdvance.query.join(Staff)
            if start_date: adv_query = adv_query.filter(SalaryAdvance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
            if end_date: adv_query = adv_query.filter(SalaryAdvance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
            if search: adv_query = adv_query.filter(Staff.name.ilike(f'%{search}%'))
            
            for a in adv_query.all():
                unified_data.append({
                    'Expense Number': f"ADV-{a.id}",
                    'Date': a.date.strftime('%Y-%m-%d'),
                    'sort_date': a.date,
                    'Category': 'Payroll Advance',
                    'Vendor/Staff': a.staff.name,
                    'Description': a.description or "Staff Advance",
                    'Amount': f"{a.amount:.2f}",
                    'Method': 'Cash'
                })
                
        # To sort correctly, we need a date object, not a string
        # Let's adjust unified_data formatting slightly
        for item in unified_data:
            if 'sort_date' not in item:
                # Regular expense objects already have date
                pass
                
        # Re-sort using Date strings (YYYY-MM-DD) which is safe for strings
        unified_data.sort(key=lambda x: x['Date'], reverse=True)
        
        title = "Expense Report"
        headers = ['Expense Number', 'Date', 'Category', 'Vendor/Staff', 'Description', 'Amount', 'Method']
        data = unified_data

    elif report_type == 'vendor':
        query = Vendor.query
        if search: query = query.filter(or_(Vendor.name.ilike(f'%{search}%'), Vendor.gst_number.ilike(f'%{search}%')))
        vendors = query.order_by(Vendor.name).all()
        title = "Vendor Report"
        headers = ['Name', 'Phone', 'Email', 'GST', 'Total Purchases', 'Outstanding']
        data = [{
            'Name': v.name,
            'Phone': v.phone,
            'Email': v.email,
            'GST': v.gst_number,
            'Total Purchases': f"{v.total_purchases:.2f}",
            'Outstanding': f"{v.outstanding_balance:.2f}"
        } for v in vendors]

    elif report_type == 'customer':
        query = Customer.query
        if search: query = query.filter(or_(Customer.name.ilike(f'%{search}%'), Customer.gst_number.ilike(f'%{search}%')))
        customers = query.order_by(Customer.name).all()
        title = "Customer Report"
        headers = ['Name', 'Phone', 'Email', 'GST', 'Total Sales', 'Outstanding']
        data = [{
            'Name': c.name,
            'Phone': c.phone,
            'Email': c.email,
            'GST': c.gst_number,
            'Total Sales': f"{c.total_sales:.2f}",
            'Outstanding': f"{c.outstanding_balance:.2f}"
        } for c in customers]

    elif report_type == 'return':
        query = SaleReturn.query
        if start_date: query = query.filter(SaleReturn.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date: query = query.filter(SaleReturn.date <= datetime.strptime(end_date, '%Y-%m-%d'))
        if status != 'all': query = query.filter(SaleReturn.status == status)
        if search: query = query.filter(SaleReturn.return_number.ilike(f'%{search}%'))
        
        returns = query.order_by(SaleReturn.date.desc()).all()
        title = "Sales Return Report"
        headers = ['Return Number', 'Date', 'Invoice', 'Customer', 'Subtotal', 'Tax', 'Total', 'Status']
        data = [{
            'Return Number': r.return_number,
            'Date': r.date.strftime('%Y-%m-%d'),
            'Invoice': r.sale.invoice_number if r.sale else '-',
            'Customer': r.customer.name if r.customer else 'Walk-in',
            'Subtotal': f"{r.subtotal:.2f}",
            'Tax': f"{r.tax:.2f}",
            'Total': f"{r.total:.2f}",
            'Status': r.status.capitalize()
        } for r in returns]

    elif report_type == 'manufacturing':
        product_id = request.args.get('product_id')
        query = ManufacturingOrder.query.join(BOM)
        if start_date: query = query.filter(ManufacturingOrder.start_date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date: query = query.filter(ManufacturingOrder.start_date <= datetime.strptime(start_date, '%Y-%m-%d'))
        if status != 'all': query = query.filter(ManufacturingOrder.status == status)
        if product_id and product_id != 'all': query = query.filter(BOM.product_id == int(product_id))
        
        orders = query.order_by(ManufacturingOrder.start_date.desc()).all()
        title = "Manufacturing Report"
        headers = ['Order Number', 'Date', 'Product', 'Quantity', 'Material Cost', 'Labor Cost', 'Overhead', 'Total Cost', 'Status']
        data = [{
            'Order Number': o.order_number,
            'Date': o.start_date.strftime('%Y-%m-%d') if o.start_date else 'N/A',
            'Product': o.bom.product.name,
            'Quantity': o.quantity_to_produce,
            'Material Cost': f"{o.actual_material_cost or 0:.2f}",
            'Labor Cost': f"{o.actual_labor_cost or 0:.2f}",
            'Overhead': f"{o.total_cost - (o.actual_material_cost or 0) - (o.actual_labor_cost or 0):.2f}" if o.total_cost else "0.00",
            'Total Cost': f"{o.total_cost or 0:.2f}",
            'Status': o.status
        } for o in orders]

    elif report_type == 'bom':
        product_id = request.args.get('product_id')
        version_filter = request.args.get('version', 'all')
        view_mode = request.args.get('view_mode', 'boms')
        
        if view_mode == 'versions':
            # Export version history
            query = BOMVersion.query
            if start_date: query = query.filter(BOMVersion.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
            if end_date: query = query.filter(BOMVersion.created_at <= datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
            
            versions = query.order_by(BOMVersion.created_at.desc()).all()
            
            # Filter by product if specified
            if product_id and product_id != 'all':
                versions = [v for v in versions if v.bom.product_id == int(product_id)]
            
            title = "BOM Version History Report"
            headers = ['BOM Name', 'Product', 'Version', 'Labor Cost', 'Overhead Cost', 'Total Cost', 'Change Reason', 'Change Type', 'Previous Version', 'Created Date']
            data = [{
                'BOM Name': v.bom.name if v.bom else 'N/A',
                'Product': v.bom.product.name if v.bom and v.bom.product else 'N/A',
                'Version': v.version_number,
                'Labor Cost': f"{v.labor_cost:.2f}",
                'Overhead Cost': f"{v.overhead_cost:.2f}",
                'Total Cost': f"{v.total_cost:.2f}",
                'Change Reason': v.change_reason or 'N/A',
                'Change Type': v.change_type or 'N/A',
                'Previous Version': v.previous_version or 'v1',
                'Created Date': v.created_at.strftime('%Y-%m-%d %H:%M') if v.created_at else 'N/A'
            } for v in versions]
        else:
            # Export current BOMs
            query = BOM.query
            if start_date: query = query.filter(BOM.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
            if end_date: query = query.filter(BOM.created_at <= datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
            if product_id and product_id != 'all': query = query.filter(BOM.product_id == int(product_id))
            if version_filter != 'all':
                if version_filter == 'active':
                    query = query.filter(BOM.is_active == True)
                else:
                    query = query.filter(BOM.is_active == False)
            
            boms = query.order_by(BOM.created_at.desc()).all()
            title = "BOM Report"
            headers = ['BOM Name', 'Product', 'Version', 'Components', 'Labor Cost', 'Overhead Cost', 'Total Cost', 'Active', 'Created Date']
            data = [{
                'BOM Name': b.name,
                'Product': b.product.name if b.product else 'N/A',
                'Version': b.version,
                'Components': len(b.items),
                'Labor Cost': f"{b.labor_cost:.2f}",
                'Overhead Cost': f"{b.overhead_cost:.2f}",
                'Total Cost': f"{b.total_cost:.2f}",
                'Active': 'Yes' if b.is_active else 'No',
                'Created Date': b.created_at.strftime('%Y-%m-%d') if b.created_at else 'N/A'
            } for b in boms]

    elif report_type == 'bom_detail':
        bom_id = request.args.get('bom_id')
        bom = BOM.query.get_or_404(int(bom_id))
        title = f"BOM Details: {bom.name}"
        headers = ['BOM Name', 'Finished Good', 'Component Name', 'Item Code', 'Qty', 'Unit Cost', 'Total Cost']
        data = [{
            'BOM Name': bom.name,
            'Finished Good': bom.product.name,
            'Component Name': item.component.name,
            'Item Code': item.component.sku,
            'Qty': item.quantity,
            'Unit Cost': f"{item.unit_cost:.2f}",
            'Total Cost': f"{item.total_cost:.2f}"
        } for item in bom.items]
        
        # Add summary rows
        data.append({
            'BOM Name': '', 'Finished Good': '', 'Component Name': 'Components Cost:', 'Item Code': '',
            'Qty': '', 'Unit Cost': '', 'Total Cost': f"{(bom.total_cost - bom.labor_cost - bom.overhead_cost):.2f}"
        })
        data.append({
            'BOM Name': '', 'Finished Good': '', 'Component Name': 'Labor Cost:', 'Item Code': '',
            'Qty': '', 'Unit Cost': '', 'Total Cost': f"{bom.labor_cost:.2f}"
        })
        data.append({
            'BOM Name': '', 'Finished Good': '', 'Component Name': 'Overhead Cost:', 'Item Code': '',
            'Qty': '', 'Unit Cost': '', 'Total Cost': f"{bom.overhead_cost:.2f}"
        })
        data.append({
            'BOM Name': '', 'Finished Good': '', 'Component Name': 'TOTAL UNIT COST:', 'Item Code': '',
            'Qty': '', 'Unit Cost': '', 'Total Cost': f"{bom.total_cost:.2f}"
        })

    elif report_type == 'salary':
        staff_id = request.args.get('staff_id')
        query = SalaryPayment.query
        if start_date: query = query.filter(SalaryPayment.payment_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date: query = query.filter(SalaryPayment.payment_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        if staff_id and staff_id != 'all': query = query.filter(SalaryPayment.staff_id == int(staff_id))
        
        payments = query.order_by(SalaryPayment.payment_date.desc()).all()
        title = "Salary Payment Report"
        headers = ['Staff', 'Designation', 'Month/Year', 'Base Salary', 'Bonus', 'Adv. Deduction', 'Other Deductions', 'Net Paid', 'Date', 'Method', 'Status']
        data = [{
            'Staff': p.staff.name,
            'Designation': p.staff.designation or 'N/A',
            'Month/Year': f"{p.month}/{p.year}",
            'Base Salary': f"{p.base_salary:.2f}",
            'Bonus': f"{p.bonus:.2f}",
            'Adv. Deduction': f"{p.advance_deduction:.2f}",
            'Other Deductions': f"{p.other_deductions:.2f}",
            'Net Paid': f"{p.net_salary:.2f}",
            'Date': p.payment_date.strftime('%Y-%m-%d'),
            'Method': p.payment_method,
            'Status': p.status.capitalize()
        } for p in payments]

    elif report_type == 'profit_loss':
        start_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else datetime.now().replace(day=1)
        end_date = datetime.strptime(end_date, '%Y-%m-%d') if end_date else datetime.now()
        
        # Aggregate data (summarized for Excel/PDF)
        # Revenue
        total_rev = db.session.query(func.sum(Sale.total)).filter(Sale.date >= start_date, Sale.date <= end_date).scalar() or 0
        total_ret = db.session.query(func.sum(SaleReturn.total)).filter(SaleReturn.date >= start_date, SaleReturn.date <= end_date).scalar() or 0
        net_rev = total_rev - total_ret
        
        # COGS
        items = SaleItem.query.join(Sale).filter(Sale.date >= start_date, Sale.date <= end_date).all()
        total_cogs = sum((i.product.cost_price or 0) * i.quantity for i in items)
        
        # Expenses
        # Operating
        total_exp = db.session.query(func.sum(Expense.amount)).filter(
            Expense.date >= start_date, 
            Expense.date <= end_date, 
            Expense.is_bom_overhead == False,
            Expense.status == 'confirmed'
        ).scalar() or 0
        salary_paid = db.session.query(func.sum(SalaryPayment.net_salary)).filter(SalaryPayment.status == 'paid', SalaryPayment.payment_date >= start_date.date(), SalaryPayment.payment_date <= end_date.date()).scalar() or 0
        salary_adv = db.session.query(func.sum(SalaryAdvance.amount)).filter(SalaryAdvance.date >= start_date.date(), SalaryAdvance.date <= end_date.date()).scalar() or 0
        
        # Informational / Inventory
        total_purchases = db.session.query(func.sum(PurchaseBill.total)).filter(PurchaseBill.date >= start_date, PurchaseBill.date <= end_date).scalar() or 0
        total_bom = db.session.query(func.sum(ManufacturingOrder.total_cost)).filter(ManufacturingOrder.status == 'Completed', ManufacturingOrder.end_date >= start_date.date(), ManufacturingOrder.end_date <= end_date.date()).scalar() or 0
        bom_overhead = db.session.query(func.sum(Expense.amount)).filter(
            Expense.date >= start_date, 
            Expense.date <= end_date, 
            Expense.is_bom_overhead == True,
            Expense.status == 'confirmed'
        ).scalar() or 0
        
        total_operating_exp = total_exp + salary_paid + salary_adv
        gross_profit = net_rev - total_cogs
        net_profit = gross_profit - total_operating_exp
        
        title = f"Profit & Loss Statement ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"
        headers = ['Account Description', 'Amount (PKR)', 'Subtotal (PKR)']
        data = [
            {'Account Description': 'REVENUE', 'Amount (PKR)': '', 'Subtotal (PKR)': f"{total_rev:.2f}"},
            {'Account Description': '  Total Sales', 'Amount (PKR)': f"{total_rev:.2f}", 'Subtotal (PKR)': ''},
            {'Account Description': '  Less: Sales Returns', 'Amount (PKR)': f"({total_ret:.2f})", 'Subtotal (PKR)': ''},
            {'Account Description': 'TOTAL NET REVENUE', 'Amount (PKR)': '', 'Subtotal (PKR)': f"{net_rev:.2f}"},
            {'Account Description': '', 'Amount (PKR)': '', 'Subtotal (PKR)': ''},
            {'Account Description': 'COST OF GOODS SOLD', 'Amount (PKR)': '', 'Subtotal (PKR)': f"({total_cogs:.2f})"},
            {'Account Description': 'GROSS PROFIT', 'Amount (PKR)': '', 'Subtotal (PKR)': f"{gross_profit:.2f}"},
            {'Account Description': '', 'Amount (PKR)': '', 'Subtotal (PKR)': ''},
            {'Account Description': 'OPERATING EXPENSES (Deducted from Profit)', 'Amount (PKR)': '', 'Subtotal (PKR)': ''},
            {'Account Description': '  General Business Expenses', 'Amount (PKR)': f"{total_exp:.2f}", 'Subtotal (PKR)': ''},
            {'Account Description': '  Payroll (Salaries & Advances)', 'Amount (PKR)': f"{salary_paid + salary_adv:.2f}", 'Subtotal (PKR)': ''},
            {'Account Description': 'TOTAL OPERATING EXPENSES', 'Amount (PKR)': '', 'Subtotal (PKR)': f"({total_operating_exp:.2f})"},
            {'Account Description': '', 'Amount (PKR)': '', 'Subtotal (PKR)': ''},
            {'Account Description': 'NET PROFIT', 'Amount (PKR)': '', 'Subtotal (PKR)': f"{net_profit:.2f}"},
            {'Account Description': '', 'Amount (PKR)': '', 'Subtotal (PKR)': ''},
            {'Account Description': 'INVENTORY & MANUFACTURING ACTIVITY (Informational)', 'Amount (PKR)': '', 'Subtotal (PKR)': ''},
            {'Account Description': '  Inventory Purchases', 'Amount (PKR)': f"{total_purchases:.2f}", 'Subtotal (PKR)': ''},
            {'Account Description': '  Manufacturing Costs', 'Amount (PKR)': f"{total_bom + bom_overhead:.2f}", 'Subtotal (PKR)': ''},
            {'Account Description': 'TOTAL SECONDARY OUTFLOW', 'Amount (PKR)': '', 'Subtotal (PKR)': f"{total_purchases + total_bom + bom_overhead:.2f}"}
        ]

    if not data:
        flash('No data available for the selected filters.', 'warning')
        return redirect(url_for(f'reports.{report_type}_report'))

    # Generate the requested format
    company_info = get_company_info()
    
    if format == 'pdf':
        output = generate_pdf(data, title, headers, company_info)
        filename = f"{report_type}_report.pdf"
        mimetype = 'application/pdf'
    elif format == 'excel':
        output = generate_excel(data, report_type.title())
        filename = f"{report_type}_report.xlsx"
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif format == 'csv':
        output = generate_csv(data)
        filename = f"{report_type}_report.csv"
        mimetype = 'text/csv'
    else:
        return jsonify({'error': 'Invalid format'}), 400

    return send_file(output, as_attachment=True, download_name=filename, mimetype=mimetype)