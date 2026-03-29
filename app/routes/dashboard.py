from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Sale, Product, PurchaseBill, Expense, db, SaleItem
from datetime import datetime, timedelta
from sqlalchemy import func

bp = Blueprint('dashboard', __name__)

@bp.route('/')
@login_required
def index():
    # Get current month's data
    current_month = datetime.now().replace(day=1)

    # Total Sales
    total_sales = db.session.query(func.sum(Sale.total)).filter(
        Sale.date >= current_month
    ).scalar() or 0

    # Total COGS
    total_cogs = db.session.query(func.sum(SaleItem.quantity * Product.cost_price))\
        .join(Sale, SaleItem.sale_id == Sale.id)\
        .join(Product, SaleItem.product_id == Product.id)\
        .filter(Sale.date >= current_month)\
        .scalar() or 0

    # Total Purchases (Inventory Addition)
    total_purchases = db.session.query(func.sum(PurchaseBill.total)).filter(
        PurchaseBill.date >= current_month
    ).scalar() or 0

    # Total Expenses
    total_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.date >= current_month
    ).scalar() or 0

    # Gross Profit = Sales - COGS
    gross_profit = total_sales - total_cogs

    # Net Profit = Gross Profit - Expenses
    net_profit = gross_profit - total_expenses

    # Outstanding Payments
    outstanding = db.session.query(func.sum(Sale.total - Sale.paid_amount)).filter(
        Sale.status != 'paid'
    ).scalar() or 0
    
    # Low Stock Products
    low_stock = Product.query.filter(Product.quantity <= Product.reorder_level).count()
    
    # Recent Sales
    recent_sales = Sale.query.order_by(Sale.date.desc()).limit(10).all()
    
    # Sales Chart Data (Last 7 days)
    sales_chart = []
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
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
                         gross_profit=gross_profit,
                         net_profit=net_profit,
                         outstanding=outstanding,
                         low_stock=low_stock,
                         recent_sales=recent_sales,
                         sales_chart=sales_chart)