from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models import Sale, Product, PurchaseBill, Expense, db, SaleItem, Vendor, Customer, SalaryPayment, SalaryAdvance
from datetime import datetime, timedelta
from sqlalchemy import func

bp = Blueprint('dashboard', __name__)

@bp.route('/')
@login_required
def index():
    # Get date filters from request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # If no dates provided, use current month
    if not start_date or not end_date:
        current_month = datetime.now().replace(day=1)
        if not start_date:
            start_date = current_month.strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Convert string dates to datetime objects
    try:
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except:
        current_month = datetime.now().replace(day=1)
        start_datetime = current_month
        end_datetime = datetime.now().replace(hour=23, minute=59, second=59)

    # Total Sales
    total_sales = db.session.query(func.sum(Sale.total)).filter(
        Sale.date >= start_datetime,
        Sale.date <= end_datetime
    ).scalar() or 0

    # Total COGS
    total_cogs = db.session.query(func.sum(SaleItem.quantity * Product.cost_price))\
        .join(Sale, SaleItem.sale_id == Sale.id)\
        .join(Product, SaleItem.product_id == Product.id)\
        .filter(Sale.date >= start_datetime, Sale.date <= end_datetime)\
        .scalar() or 0

    # Total Purchases (Inventory Addition)
    total_purchases = db.session.query(func.sum(PurchaseBill.total)).filter(
        PurchaseBill.date >= start_datetime,
        PurchaseBill.date <= end_datetime
    ).scalar() or 0

    # Total Operating Expenses (Non-BOM)
    operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.is_bom_overhead == False,
        Expense.date >= start_datetime,
        Expense.date <= end_datetime
    ).scalar() or 0

    # Total Manufacturing Overhead (BOM linked)
    manufacturing_overhead = db.session.query(func.sum(Expense.amount)).filter(
        Expense.is_bom_overhead == True,
        Expense.date >= start_datetime,
        Expense.date <= end_datetime
    ).scalar() or 0
    # Total Payroll (Payments + Advances given in period)
    total_payments = db.session.query(func.sum(SalaryPayment.net_salary)).filter(
        SalaryPayment.status == 'paid',
        SalaryPayment.payment_date >= start_datetime.date(),
        SalaryPayment.payment_date <= end_datetime.date()
    ).scalar() or 0
    
    total_advances = db.session.query(func.sum(SalaryAdvance.amount)).filter(
        SalaryAdvance.date >= start_datetime.date(),
        SalaryAdvance.date <= end_datetime.date()
    ).scalar() or 0
    
    total_payroll = total_payments + total_advances
    
    total_expenses = operating_expenses + manufacturing_overhead + total_payroll

    # Gross Profit = Sales - COGS
    gross_profit = total_sales - total_cogs

    # Net Profit = Gross Profit - operating_expenses - total_payroll
    # (BOM overhead is already in COGS)
    net_profit = gross_profit - operating_expenses - total_payroll

    # Outstanding Payments
    outstanding = db.session.query(func.sum(Sale.total - Sale.paid_amount)).filter(
        Sale.status != 'paid',
        Sale.date >= start_datetime,
        Sale.date <= end_datetime
    ).scalar() or 0
    
    # Low Stock Products
    low_stock = Product.query.filter(Product.quantity <= Product.reorder_level).count()
    
    # Total Products
    products_count = Product.query.count()
    
    # Active Vendors
    vendors_count = Vendor.query.filter(Vendor.is_active == True).count()
    
    # Active Customers
    customers_count = Customer.query.filter(Customer.is_active == True).count()
    
    # Recent Sales
    recent_sales = Sale.query.filter(
        Sale.date >= start_datetime,
        Sale.date <= end_datetime
    ).order_by(Sale.date.desc()).limit(10).all()
    
    # Sales Chart Data (Last 7 days from end_date)
    sales_chart = []
    chart_end = end_datetime if end_datetime.date() <= datetime.now().date() else datetime.now()
    for i in range(6, -1, -1):
        date = chart_end - timedelta(days=i)
        day_sales = db.session.query(func.sum(Sale.total)).filter(
            func.date(Sale.date) == date.date()
        ).scalar() or 0
        sales_chart.append({
            'date': date.strftime('%Y-%m-%d'),
            'amount': day_sales
        })
    
    return render_template('dashboard/index.html',
                         total_sales=total_sales,
                         total_purchases=total_purchases,
                         total_cogs=total_cogs,
                         total_expenses=total_expenses,
                         operating_expenses=operating_expenses,
                         manufacturing_overhead=manufacturing_overhead,
                         total_payroll=total_payroll,
                         gross_profit=gross_profit,
                         net_profit=net_profit,
                         outstanding=outstanding,
                         low_stock=low_stock,
                         products_count=products_count,
                         vendors_count=vendors_count,
                         customers_count=customers_count,
                         recent_sales=recent_sales,
                         sales_chart=sales_chart,
                         start_date=start_date,
                         end_date=end_date)