from flask import Blueprint, render_template, request
from app.utils import permission_required
from flask_login import login_required, current_user
from app.models import Sale, Product, ProductCategory, PurchaseBill, PurchaseItem, Expense, ExpenseCategory, db, SaleItem, Vendor, Customer, Staff, Attendance
from datetime import datetime, timedelta
from sqlalchemy import func, inspect
from calendar import monthrange

bp = Blueprint('dashboard', __name__)

def has_column(table_name, column_name):
    try:
        inspector = inspect(db.engine)
        return column_name in [c['name'] for c in inspector.get_columns(table_name)]
    except:
        return False

@bp.route('/')
@login_required
def index():
    # Only Admin or users with specific permission can view the main dashboard
    from flask import redirect, url_for, flash
    if current_user.role != 'admin' and not getattr(current_user, 'can_view_dashboard', False):
        flash('General Dashboard is restricted to Admin only.', 'info')
        # Redirect to a module they are likely to have access to, or just purchase list
        return redirect(url_for('purchase.purchase_orders'))

    # Make sure any fixed-expense cycle that has started is in the book before
    # the totals are computed. Self-guarding — never raises.
    try:
        from app.routes.accounting import ensure_fixed_expense_rows
        ensure_fixed_expense_rows()
    except Exception:
        pass

    # Get date filters from request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    all_time = request.args.get('all_time', '0') == '1'

    if all_time:
        # Reset: show all-time data — use widest possible range
        start_datetime = datetime(2000, 1, 1)
        end_datetime = datetime.now().replace(hour=23, minute=59, second=59)
        start_date = ''
        end_date = ''
    else:
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

    # Total Sales — only count admin-approved invoices
    total_sales = db.session.query(func.sum(Sale.total)).filter(
        Sale.is_approved == True,
        Sale.is_rejected == False,
        Sale.status != 'cancelled',
        Sale.date >= start_datetime,
        Sale.date <= end_datetime
    ).scalar() or 0

    # Total COGS — only from approved invoices
    total_cogs = db.session.query(func.sum(SaleItem.quantity * Product.cost_price))\
        .join(Sale, SaleItem.sale_id == Sale.id)\
        .join(Product, SaleItem.product_id == Product.id)\
        .filter(
            Sale.is_approved == True,
            Sale.is_rejected == False,
            Sale.status != 'cancelled',
            Sale.date >= start_datetime,
            Sale.date <= end_datetime
        )\
        .scalar() or 0

    # Total Purchases (Inventory Addition)
    total_purchases = db.session.query(func.sum(PurchaseBill.total)).filter(
        PurchaseBill.is_approved == True,
        PurchaseBill.is_rejected == False,
        PurchaseBill.status != 'cancelled',
        PurchaseBill.date >= start_datetime,
        PurchaseBill.date <= end_datetime
    ).scalar() or 0

    # Exclude expenses that were only recorded as a transfer to a Sale/Purchase
    # payment (not a real cost) — see Expense.is_payment_transfer.
    transfer_filter = [Expense.is_payment_transfer == False] if has_column('expenses', 'is_payment_transfer') else []

    # Total Operating Expenses (Non-BOM, Non-Divided) - handle missing column gracefully
    if has_column('expenses', 'is_bom_overhead'):
        if has_column('expenses', 'is_monthly_divided'):
            # Exclude both BOM and divided expenses
            operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.is_bom_overhead == False,
                Expense.is_monthly_divided == False,
                Expense.is_shifted == False,
                Expense.is_inventory_shifted == False,
                Expense.date >= start_datetime,
                Expense.date <= end_datetime,
                Expense.status == 'confirmed',
                *transfer_filter
            ).scalar() or 0

            # Total Manufacturing Overhead (BOM linked, non-divided)
            manufacturing_overhead = db.session.query(func.sum(Expense.amount)).filter(
                Expense.is_bom_overhead == True,
                Expense.is_monthly_divided == False,
                Expense.is_shifted == False,
                Expense.is_inventory_shifted == False,
                Expense.date >= start_datetime,
                Expense.date <= end_datetime,
                Expense.status == 'confirmed',
                *transfer_filter
            ).scalar() or 0
        else:
            # Fallback: exclude BOM only
            operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.is_bom_overhead == False,
                Expense.is_shifted == False,
                Expense.is_inventory_shifted == False,
                Expense.date >= start_datetime,
                Expense.date <= end_datetime,
                Expense.status == 'confirmed',
                *transfer_filter
            ).scalar() or 0

            # Total Manufacturing Overhead (BOM linked)
            manufacturing_overhead = db.session.query(func.sum(Expense.amount)).filter(
                Expense.is_bom_overhead == True,
                Expense.is_shifted == False,
                Expense.is_inventory_shifted == False,
                Expense.date >= start_datetime,
                Expense.date <= end_datetime,
                Expense.status == 'confirmed',
                *transfer_filter
            ).scalar() or 0
    else:
        # Fallback: is_bom_overhead doesn't exist
        if has_column('expenses', 'is_monthly_divided'):
            # Exclude divided expenses only
            operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.is_monthly_divided == False,
                Expense.is_shifted == False,
                Expense.is_inventory_shifted == False,
                Expense.date >= start_datetime,
                Expense.date <= end_datetime,
                Expense.status == 'confirmed',
                *transfer_filter
            ).scalar() or 0
        else:
            # Fallback: include all expenses
            operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.is_shifted == False,
                Expense.is_inventory_shifted == False,
                Expense.date >= start_datetime,
                Expense.date <= end_datetime,
                Expense.status == 'confirmed',
                *transfer_filter
            ).scalar() or 0
        manufacturing_overhead = 0
    
    # Calculate monthly divided expenses - proportional for the period
    divided_expenses_for_period = 0
    if has_column('expenses', 'is_monthly_divided'):
        monthly_expenses = Expense.query.filter(
            Expense.is_monthly_divided == True,
            Expense.is_shifted == False,
            Expense.is_inventory_shifted == False,
            Expense.status == 'confirmed',
            *transfer_filter
        ).all()
        for exp in monthly_expenses:
            if exp.monthly_start_date and exp.monthly_end_date:
                # Find overlap between expense period and filter period
                overlap_start = max(exp.monthly_start_date, start_datetime.date())
                overlap_end = min(exp.monthly_end_date, end_datetime.date())
                
                if overlap_start <= overlap_end:
                    # Calculate days in overlap
                    overlap_days = (overlap_end - overlap_start).days + 1
                    # Add proportional amount
                    divided_expenses_for_period += exp.daily_amount * overlap_days
    
    # Calculate Daily Payroll (Active staff daily salary × days in period + Attendance-based salary)
    # Note: Payroll is not shifted, so no change needed here
    
    # Calculate Tools Expenses separately
    tools_expenses = db.session.query(func.sum(Expense.amount)).join(ExpenseCategory).filter(
        ExpenseCategory.name == 'Tools Expense',
        Expense.is_shifted == False,
        Expense.is_inventory_shifted == False,
        Expense.date >= start_datetime,
        Expense.date <= end_datetime,
        Expense.status == 'confirmed',
        *transfer_filter
    ).scalar() or 0
    
    # Subtract tools_expenses from operating_expenses to avoid double counting in display
    # (operating_expenses already contains ALL non-BOM, non-divided expenses)
    operating_expenses = operating_expenses - tools_expenses
    
    # Calculate Daily Payroll (Active staff daily salary × days in period + Attendance-based salary)
    daily_payroll_for_period = 0
    
    # Get attendance records for the period
    attendance_records_by_date = {}
    if 'attendance' in [t for t in inspect(db.engine).get_table_names()]:
        attendance_records = Attendance.query.filter(
            Attendance.date >= start_datetime.date(),
            Attendance.date <= end_datetime.date()
        ).all()
        
        # Organize by date for easy lookup
        for record in attendance_records:
            if record.date not in attendance_records_by_date:
                attendance_records_by_date[record.date] = []
            attendance_records_by_date[record.date].append(record)
        
        # Add attendance-based salary from time tracking
        attendance_payroll = sum(record.earned_amount for record in attendance_records)
        daily_payroll_for_period += attendance_payroll
    
    # Then add daily salary for active staff ONLY for days without attendance records
    active_staff = Staff.query.filter_by(is_active=True).all()
    for staff in active_staff:
        # Calculate salary for the period considering actual days in each month
        period_start = start_datetime.date()
        period_end = end_datetime.date()
        
        # If entire period is within same month, use that month's day count
        if period_start.month == period_end.month and period_start.year == period_end.year:
            # Single month period
            days_in_period = (period_end - period_start).days + 1
            _, days_in_month = monthrange(period_start.year, period_start.month)
            daily_rate = staff.monthly_salary / float(days_in_month)
            
            # Count only days without attendance records
            days_without_attendance = 0
            current_date = period_start
            while current_date <= period_end:
                if current_date not in attendance_records_by_date:
                    days_without_attendance += 1
                current_date += timedelta(days=1)
            
            staff_payroll = daily_rate * days_without_attendance
            daily_payroll_for_period += staff_payroll
        else:
            # Multi-month period - calculate for each month separately
            current_date = period_start
            while current_date <= period_end:
                _, days_in_month = monthrange(current_date.year, current_date.month)
                
                # Calculate the end of this month or end of period (whichever is earlier)
                month_end = datetime(
                    current_date.year,
                    current_date.month,
                    days_in_month
                ).date()
                actual_end = min(month_end, period_end)
                
                # Daily rate for this month
                daily_rate = staff.monthly_salary / float(days_in_month)
                
                # Count only days without attendance records in this month's portion
                days_without_attendance = 0
                check_date = current_date
                while check_date <= actual_end:
                    if check_date not in attendance_records_by_date:
                        days_without_attendance += 1
                    check_date += timedelta(days=1)
                
                staff_payroll = daily_rate * days_without_attendance
                daily_payroll_for_period += staff_payroll
                
                # Move to next month
                if actual_end == month_end:
                    current_date = datetime(
                        current_date.year if current_date.month < 12 else current_date.year + 1,
                        (current_date.month % 12) + 1,
                        1
                    ).date()
                else:
                    break
    
    # Total expenses = operating + tools + manufacturing overhead + daily payroll + divided (proportional)
    total_expenses = operating_expenses + tools_expenses + manufacturing_overhead + daily_payroll_for_period + divided_expenses_for_period

    # Gross Profit = Sales - COGS
    gross_profit = total_sales - total_cogs

    # Net Profit = Gross Profit - all expenses (operating + tools + divided proportional + payroll)
    # (BOM overhead is already in COGS)
    net_profit = gross_profit - operating_expenses - tools_expenses - divided_expenses_for_period - daily_payroll_for_period

    # Outstanding Payments — ALL unpaid invoices regardless of date (snapshot, not period metric)
    outstanding = db.session.query(func.sum(Sale.total - Sale.paid_amount)).filter(
        Sale.is_approved == True,
        Sale.is_rejected == False,
        Sale.status != 'cancelled',
        Sale.status != 'paid'
    ).scalar() or 0
    
    # Low Stock Products
    low_stock = Product.query.filter(Product.quantity <= Product.reorder_level).count()
    
    # Total Products
    products_count = Product.query.count()
    
    # Category filter for Total Stock Value
    selected_category_id = request.args.get('category_id', '', type=str)
    categories = ProductCategory.query.filter_by(is_active=True).order_by(ProductCategory.name).all()

    # Total Stock Value — always current live inventory (snapshot), optionally filtered by category
    stock_q = db.session.query(func.sum(Product.quantity * Product.cost_price))
    if selected_category_id and selected_category_id.isdigit():
        stock_q = stock_q.filter(Product.category_id == int(selected_category_id))
    total_stock_value = stock_q.scalar() or 0
    
    # Active Vendors
    vendors_count = Vendor.query.filter(Vendor.is_active == True).count()
    
    # Active Customers
    customers_count = Customer.query.filter(Customer.is_active == True).count()
    
    # Recent Sales
    recent_sales = Sale.query.filter(
        Sale.is_approved == True,
        Sale.is_rejected == False,
        Sale.status != 'cancelled',
        Sale.date >= start_datetime,
        Sale.date <= end_datetime
    ).order_by(Sale.date.desc()).limit(10).all()
    
    # Sales Chart Data (Last 7 days from end_date)
    sales_chart = []
    chart_end = end_datetime if end_datetime.date() <= datetime.now().date() else datetime.now()
    for i in range(6, -1, -1):
        date = chart_end - timedelta(days=i)
        day_sales = db.session.query(func.sum(Sale.total)).filter(
            Sale.is_approved == True,
            Sale.is_rejected == False,
            Sale.status != 'cancelled',
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
                         tools_expenses=tools_expenses,
                         manufacturing_overhead=manufacturing_overhead,
                         daily_payroll_for_period=daily_payroll_for_period,
                         divided_expenses_for_period=divided_expenses_for_period,
                         gross_profit=gross_profit,
                         net_profit=net_profit,
                         outstanding=outstanding,
                         low_stock=low_stock,
                         products_count=products_count,
                         total_stock_value=total_stock_value,
                         categories=categories,
                         selected_category_id=selected_category_id,
                         vendors_count=vendors_count,
                         customers_count=customers_count,
                         recent_sales=recent_sales,
                         sales_chart=sales_chart,
                         start_date=start_date,
                         end_date=end_date,
                         all_time=all_time)