from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models import Sale, PurchaseBill, Transaction, Expense, ExpenseCategory, Vendor, Account, Payment, TaxRate, Currency, RecurringExpense
from app.forms import ExpenseForm, ExpenseCategoryForm
from datetime import datetime, timedelta
from sqlalchemy import func, and_, inspect

bp = Blueprint('accounting', __name__)

def has_column(table_name, column_name):
    try:
        inspector = inspect(db.engine)
        return column_name in [c['name'] for c in inspector.get_columns(table_name)]
    except:
        return False

@bp.route('/ledger')
def ledger():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    account = request.args.get('account', 'all')
    
    # Build query
    query = db.session.query(Transaction)
    
    if start_date:
        query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d'))
    if account != 'all':
        query = query.filter(Transaction.account == account)
    
    transactions = query.order_by(Transaction.date.desc()).all()
    
    # Get unique accounts for filter
    accounts = db.session.query(Transaction.account).distinct().all()
    accounts = [a[0] for a in accounts if a[0]]
    
    # Calculate balances
    total_debit = sum(t.debit for t in transactions)
    total_credit = sum(t.credit for t in transactions)
    
    return render_template('accounting/ledger.html',
                         transactions=transactions,
                         accounts=accounts,
                         total_debit=total_debit,
                         total_credit=total_credit,
                         start_date=start_date,
                         end_date=end_date,
                         current_account=account)


@bp.route('/')
@login_required
def dashboard():
    from flask import request
    from datetime import datetime, timedelta

    # Get date filters from request
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')

    # Set default date range (last 30 days) if not provided
    if not date_from_str:
        date_from = datetime.utcnow() - timedelta(days=30)
    else:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d')

    if not date_to_str:
        date_to = datetime.utcnow()
    else:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d')

    # Apply date filters to all queries
    sales_query = Sale.query.filter(Sale.date >= date_from, Sale.date <= date_to)
    purchases_query = PurchaseBill.query.filter(PurchaseBill.date >= date_from, PurchaseBill.date <= date_to)
    expenses_query = Expense.query.filter(Expense.date >= date_from, Expense.date <= date_to)

    from app.models import SaleItem, Product
    total_sales = db.session.query(func.sum(Sale.total)).filter(Sale.date >= date_from, Sale.date <= date_to).scalar() or 0
    
    # Calculate COGS (Cost of Goods Sold)
    total_cogs = db.session.query(func.sum(SaleItem.quantity * Product.cost_price))\
        .join(Sale, SaleItem.sale_id == Sale.id)\
        .join(Product, SaleItem.product_id == Product.id)\
        .filter(Sale.date >= date_from, Sale.date <= date_to)\
        .scalar() or 0
        
    total_purchases = db.session.query(func.sum(PurchaseBill.total)).filter(PurchaseBill.date >= date_from, PurchaseBill.date <= date_to).scalar() or 0
    
    # Total Operating Expenses (Non-BOM) - handle missing column gracefully
    if has_column('expenses', 'is_bom_overhead'):
        operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
            Expense.is_bom_overhead == False,
            Expense.date >= date_from,
            Expense.date <= date_to
        ).scalar() or 0

        # Total Manufacturing Overhead (BOM linked)
        manufacturing_overhead = db.session.query(func.sum(Expense.amount)).filter(
            Expense.is_bom_overhead == True,
            Expense.date >= date_from,
            Expense.date <= date_to
        ).scalar() or 0
    else:
        # Fallback: include all expenses
        operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
            Expense.date >= date_from,
            Expense.date <= date_to
        ).scalar() or 0
        manufacturing_overhead = 0
    
    total_expenses = operating_expenses + manufacturing_overhead

    # Gross Profit = Sales - COGS
    gross_profit = total_sales - total_cogs

    # Net Profit = Gross Profit - operating_expenses
    # (BOM overhead is already in COGS, so we only subtract operating expenses here)
    net_profit = gross_profit - operating_expenses

    outstanding_invoices = db.session.query(func.sum(Sale.total - Sale.paid_amount)).filter(Sale.status != 'paid', Sale.date >= date_from, Sale.date <= date_to).scalar() or 0
    paid_invoices = sales_query.filter(Sale.status == 'paid').count()
    unpaid_or_partial_invoices = sales_query.filter(Sale.status != 'paid').count()

    account_summary = {}
    transactions = Transaction.query.filter(Transaction.date >= date_from, Transaction.date <= date_to).all()
    for t in transactions:
        account_summary.setdefault(t.account, {'debit': 0, 'credit': 0})
        account_summary[t.account]['debit'] += t.debit
        account_summary[t.account]['credit'] += t.credit

    # Monthly trends within date range
    monthly_sales = []
    monthly_expenses = []
    monthly_labels = []

    # Generate monthly data for the selected date range
    current_date = date_from.replace(day=1)
    while current_date <= date_to:
        month_sales = db.session.query(func.sum(Sale.total)).filter(
            func.extract('year', Sale.date) == current_date.year,
            func.extract('month', Sale.date) == current_date.month
        ).scalar() or 0

        month_expenses = db.session.query(func.sum(Expense.amount)).filter(
            func.extract('year', Expense.date) == current_date.year,
            func.extract('month', Expense.date) == current_date.month
        ).scalar() or 0

        monthly_sales.append(float(month_sales))
        monthly_expenses.append(float(month_expenses))
        monthly_labels.append(current_date.strftime('%b %Y'))

        # Move to next month
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)

    # Yearly summary within date range
    yearly = []
    start_year = date_from.year
    end_year = date_to.year

    for y in range(start_year, end_year + 1):
        y_sales = db.session.query(func.sum(Sale.total)).filter(
            func.extract('year', Sale.date) == y
        ).scalar() or 0
        y_exp = db.session.query(func.sum(Expense.amount)).filter(
            func.extract('year', Expense.date) == y
        ).scalar() or 0
        yearly.append({'year': y, 'sales': float(y_sales), 'expenses': float(y_exp)})

    return render_template('accounting/dashboard.html',
                         total_sales=total_sales,
                         total_purchases=total_purchases,
                         total_cogs=total_cogs,
                         total_expenses=total_expenses,
                         gross_profit=gross_profit,
                         net_profit=net_profit,
                         outstanding_invoices=outstanding_invoices,
                         paid_invoices=paid_invoices,
                         unpaid_or_partial_invoices=unpaid_or_partial_invoices,
                         account_summary=account_summary,
                         monthly_sales=monthly_sales,
                         monthly_expenses=monthly_expenses,
                         monthly_labels=monthly_labels,
                         yearly=yearly,
                         date_from=date_from.strftime('%Y-%m-%d'),
                         date_to=date_to.strftime('%Y-%m-%d'))


@bp.route('/accounts')
@login_required
def accounts():
    accounts = Account.query.order_by(Account.code.nullslast(), Account.name).all()
    return render_template('accounting/accounts.html', accounts=accounts)


@bp.route('/account/add', methods=['GET', 'POST'])
@login_required
def add_account():
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        typ = request.form.get('type')
        parent_id = request.form.get('parent_id') or None
        description = request.form.get('description')
        if name and typ:
            account = Account(name=name, code=code, type=typ, parent_id=parent_id if parent_id else None, description=description)
            db.session.add(account)
            db.session.commit()
            flash('Account created successfully', 'success')
            return redirect(url_for('accounting.accounts'))
        flash('Please provide required fields', 'danger')
    parents = Account.query.filter_by(parent_id=None).order_by(Account.name).all()
    return render_template('accounting/add_account.html', parents=parents)


@bp.route('/account/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_account(id):
    account = Account.query.get_or_404(id)
    if request.method == 'POST':
        account.name = request.form.get('name')
        account.code = request.form.get('code')
        account.type = request.form.get('type')
        account.parent_id = request.form.get('parent_id') or None
        account.description = request.form.get('description')
        db.session.commit()
        flash('Account updated successfully', 'success')
        return redirect(url_for('accounting.accounts'))
    parents = Account.query.filter(Account.id != account.id, Account.parent_id == None).order_by(Account.name).all()
    return render_template('accounting/edit_account.html', account=account, parents=parents)


@bp.route('/account/<int:id>/delete', methods=['POST'])
@login_required
def delete_account(id):
    account = Account.query.get_or_404(id)
    db.session.delete(account)
    db.session.commit()
    flash('Account deleted successfully', 'success')
    return redirect(url_for('accounting.accounts'))


@bp.route('/journal')
@login_required
def journal():
    return redirect(url_for('accounting.ledger'))


@bp.route('/chart-of-accounts')
@login_required
def chart_of_accounts():
    account_balances = {}
    for t in Transaction.query.all():
        account_balances.setdefault(t.account, {'debit': 0, 'credit': 0})
        account_balances[t.account]['debit'] += t.debit
        account_balances[t.account]['credit'] += t.credit

    return render_template('accounting/chart_of_accounts.html', account_balances=account_balances)


@bp.route('/transactions')
@login_required
def transactions():
    accounts = Account.query.order_by(Account.name).all()
    invoices = Sale.query.order_by(Sale.date.desc()).all()

    # Filters
    invoice_id = request.args.get('invoice_id', type=int)
    payment_mode = request.args.get('payment_mode')
    status = request.args.get('status')
    type_filter = request.args.get('type', 'all')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    search = request.args.get('search', '').strip()
    per_page = request.args.get('per_page', 25, type=int)
    page = request.args.get('page', 1, type=int)

    # Collect all payments from different modules
    payments = []

    # Sales payments
    sales_payments = Payment.query.filter(Payment.invoice_id.isnot(None)).all()
    for p in sales_payments:
        txn = Transaction.query.filter(Transaction.reference_type == 'sale', Transaction.reference_id == p.invoice_id).first()
        payments.append({
            'id': p.id,
            'date': p.date,
            'amount': p.amount,
            'payment_mode': p.method,
            'reference_type': 'sale',
            'reference_id': p.invoice_id,
            'invoice': p.invoice,
            'debit_account': txn.debit_account if txn else None,
            'credit_account': txn.credit_account if txn else None,
            'status': txn.status if txn else 'Pending',
            'is_mapped': txn.is_mapped if txn else False,
            'description': p.notes,
            'transaction_id': txn.id if txn else None
        })

    # Expense payments
    expense_payments = Payment.query.filter(Payment.expense_id.isnot(None)).all()
    for p in expense_payments:
        txn = Transaction.query.filter(Transaction.reference_type == 'expense', Transaction.reference_id == p.expense_id).first()
        payments.append({
            'id': p.id,
            'date': p.date,
            'amount': p.amount,
            'payment_mode': p.method,
            'reference_type': 'expense',
            'reference_id': p.expense_id,
            'invoice': None,
            'debit_account': txn.debit_account if txn else None,
            'credit_account': txn.credit_account if txn else None,
            'status': txn.status if txn else 'Pending',
            'is_mapped': txn.is_mapped if txn else False,
            'description': p.notes,
            'transaction_id': txn.id if txn else None
        })

    # Purchase payments (from bills with paid_amount)
    purchase_bills = PurchaseBill.query.filter(PurchaseBill.paid_amount > 0).all()
    for bill in purchase_bills:
        txn = Transaction.query.filter(Transaction.reference_type == 'purchase', Transaction.reference_id == bill.id).first()
        payments.append({
            'id': bill.id,
            'date': bill.date,
            'amount': bill.paid_amount,
            'payment_mode': 'Various',
            'reference_type': 'purchase',
            'reference_id': bill.id,
            'invoice': None,
            'debit_account': txn.debit_account if txn else None,
            'credit_account': txn.credit_account if txn else None,
            'status': txn.status if txn else 'Pending',
            'is_mapped': txn.is_mapped if txn else False,
            'description': f'Payment for bill {bill.bill_number}',
            'transaction_id': txn.id if txn else None
        })

    # General payments
    general_payments = Payment.query.filter(Payment.invoice_id.is_(None), Payment.expense_id.is_(None)).all()
    for p in general_payments:
        txn = Transaction.query.filter(Transaction.reference_type == 'payment', Transaction.reference_id == p.id).first()
        payments.append({
            'id': p.id,
            'date': p.date,
            'amount': p.amount,
            'payment_mode': p.method,
            'reference_type': 'payment',
            'reference_id': p.id,
            'invoice': None,
            'debit_account': txn.debit_account if txn else None,
            'credit_account': txn.credit_account if txn else None,
            'status': txn.status if txn else 'Pending',
            'is_mapped': txn.is_mapped if txn else False,
            'description': p.notes,
            'transaction_id': txn.id if txn else None
        })

    # Apply filters
    if type_filter and type_filter != 'all':
        payments = [p for p in payments if p['reference_type'] == type_filter]

    if invoice_id:
        payments = [p for p in payments if p['reference_type'] == 'sale' and p['reference_id'] == invoice_id]

    if payment_mode:
        payments = [p for p in payments if p['payment_mode'] == payment_mode]

    if status:
        payments = [p for p in payments if p['status'] == status]

    if date_from:
        date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
        payments = [p for p in payments if p['date'] >= date_from_dt]

    if date_to:
        date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
        payments = [p for p in payments if p['date'] <= date_to_dt]

    if search:
        payments = [p for p in payments if search.lower() in (p['description'] or '').lower() or search.lower() in (p['payment_mode'] or '').lower()]

    # Sort by date desc
    payments.sort(key=lambda x: x['date'], reverse=True)

    # Paginate
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = payments[start:end]

    # Create a simple pagination object
    total = len(payments)
    pages = (total + per_page - 1) // per_page
    pagination = type('Pagination', (), {
        'items': paginated_items,
        'page': page,
        'pages': pages,
        'per_page': per_page,
        'total': total,
        'has_prev': page > 1,
        'has_next': page < pages,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page < pages else None
    })()

    return render_template('accounting/transactions.html',
                         transactions=paginated_items,
                         accounts=accounts,
                         invoices=invoices,
                         pagination=pagination,
                         invoice_id=invoice_id,
                         payment_mode=payment_mode,
                         status=status,
                         type=type_filter,
                         date_from=date_from,
                         date_to=date_to,
                         search=search,
                         per_page=per_page)


@bp.route('/reports/profit-loss')
@login_required
def report_profit_loss():
    # reuse existing profit_loss logic
    return redirect(url_for('accounting.profit_loss'))


@bp.route('/reports/balance-sheet')
@login_required
def report_balance_sheet():
    # simple balance sheet from account totals
    accounts = Account.query.all()
    asset = liability = equity = income = expense = 0
    for a in accounts:
        t = Transaction.query.filter(Transaction.account == a.name).all()
        balance = sum(x.debit - x.credit for x in t)
        if a.type == 'Asset':
            asset += balance
        elif a.type == 'Liability':
            liability += balance
        elif a.type == 'Equity':
            equity += balance
        elif a.type == 'Income':
            income += balance
        elif a.type == 'Expense':
            expense += balance
    return render_template('accounting/report_balance_sheet.html', asset=asset, liability=liability, equity=equity, income=income, expense=expense)


@bp.route('/reports/cash-flow')
@login_required
def report_cash_flow():
    # placeholder for cash flow
    return render_template('accounting/report_cash_flow.html')


@bp.route('/reports/expense')
@login_required
def report_expense():
    expenses = Expense.query.order_by(Expense.date.desc()).all()
    return render_template('accounting/report_expense.html', expenses=expenses)


@bp.route('/reports/tax-summary')
@login_required
def report_tax_summary():
    taxes = TaxRate.query.all()
    return render_template('accounting/report_tax_summary.html', taxes=taxes)


@bp.route('/transaction/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    accounts = Account.query.order_by(Account.name).all()
    invoices = Sale.query.order_by(Sale.invoice_number).all()
    now = datetime.utcnow().strftime('%Y-%m-%d')
    
    # Pre-fill from query params
    prefill = {
        'reference_type': request.args.get('reference_type'),
        'reference_id': request.args.get('reference_id'),
        'amount': request.args.get('amount'),
        'payment_mode': request.args.get('payment_mode'),
        'description': request.args.get('description')
    }
    
    if request.method == 'POST':
        tn = request.form.get('transaction_number')
        date = request.form.get('date')
        amount = float(request.form.get('amount') or 0)
        reference_type = request.form.get('reference_type')
        reference_id = request.form.get('reference_id') or None
        status = request.form.get('status', 'Pending')
        payment_mode = request.form.get('payment_mode', 'Cash')
        description = request.form.get('description')
        debit_account = request.form.get('debit_account')
        credit_account = request.form.get('credit_account')
        account = request.form.get('account')
        is_mapped = bool(reference_id)
        debit = float(request.form.get('debit') or 0)
        credit = float(request.form.get('credit') or 0)

        transaction = Transaction(
            transaction_number=tn,
            date=datetime.strptime(date, '%Y-%m-%d') if date else datetime.utcnow(),
            amount=amount,
            payment_mode=payment_mode,
            invoice_id=int(reference_id) if reference_type == 'sale' and reference_id else None,
            status=status,
            is_mapped=is_mapped,
            reference_type=reference_type,
            reference_id=int(reference_id) if reference_id else None,
            debit_account=debit_account,
            credit_account=credit_account,
            description=description,
            account=account,
            debit=debit,
            credit=credit
        )
        db.session.add(transaction)
        db.session.commit()
        flash('Transaction mapped', 'success')
        return redirect(url_for('accounting.transactions'))
    return render_template('accounting/add_transaction.html', accounts=accounts, invoices=invoices, now=now, prefill=prefill)
    
@bp.route('/transaction/<int:id>/delete', methods=['POST'])
@login_required
def delete_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    try:
        db.session.delete(transaction)
        db.session.commit()
        flash('Transaction mapping removed successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting transaction: {str(e)}', 'error')
    return redirect(url_for('accounting.transactions'))


@bp.route('/map_transaction/<int:payment_id>/<ref_type>')
@login_required
def map_transaction(payment_id, ref_type):
    # Redirect to add_transaction with pre-filled data
    if ref_type == 'sale':
        payment = Payment.query.get_or_404(payment_id)
        invoice = Sale.query.get(payment.invoice_id)
        return redirect(url_for('accounting.add_transaction', 
                               reference_type='sale', 
                               reference_id=payment.invoice_id,
                               amount=payment.amount,
                               payment_mode=payment.method,
                               description=f'Payment for invoice {invoice.invoice_number}' if invoice else payment.notes))
    elif ref_type == 'expense':
        payment = Payment.query.get_or_404(payment_id)
        expense = Expense.query.get(payment.expense_id)
        return redirect(url_for('accounting.add_transaction', 
                               reference_type='expense', 
                               reference_id=payment.expense_id,
                               amount=payment.amount,
                               payment_mode=payment.method,
                               description=f'Payment for expense {expense.expense_number}' if expense else payment.notes))
    elif ref_type == 'purchase':
        bill = PurchaseBill.query.get_or_404(payment_id)
        return redirect(url_for('accounting.add_transaction', 
                               reference_type='purchase', 
                               reference_id=bill.id,
                               amount=bill.paid_amount,
                               payment_mode='Various',
                               description=f'Payment for bill {bill.bill_number}'))
    elif ref_type == 'payment':
        payment = Payment.query.get_or_404(payment_id)
        return redirect(url_for('accounting.add_transaction', 
                               reference_type='payment', 
                               reference_id=payment.id,
                               amount=payment.amount,
                               payment_mode=payment.method,
                               description=payment.notes))
    return redirect(url_for('accounting.transactions'))
    return redirect(url_for('accounting.transactions'))


@bp.route('/payments')
@login_required
def payments():
    payments = Payment.query.order_by(Payment.date.desc()).all()
    return render_template('accounting/payments.html', payments=payments)


@bp.route('/payment/add', methods=['GET', 'POST'])
@login_required
def add_payment():
    invoices = Sale.query.filter(Sale.status != 'paid').all()
    if request.method == 'POST':
        payment_number = request.form.get('payment_number')
        date = request.form.get('date')
        amount = float(request.form.get('amount') or 0)
        method = request.form.get('method')
        invoice_id = request.form.get('invoice_id') or None
        reference_number = request.form.get('reference_number')
        notes = request.form.get('notes')

        payment = Payment(
            payment_number=payment_number,
            date=datetime.strptime(date, '%Y-%m-%d') if date else datetime.utcnow(),
            amount=amount,
            method=method,
            invoice_id=invoice_id if invoice_id else None,
            reference_number=reference_number,
            notes=notes
        )
        db.session.add(payment)

        if invoice_id:
            sale = Sale.query.get(int(invoice_id))
            if sale:
                sale.paid_amount += amount
                sale.update_status()

        db.session.commit()
        flash('Payment recorded', 'success')
        return redirect(url_for('accounting.payments'))
    return render_template('accounting/add_payment.html', invoices=invoices, date_today=datetime.utcnow().strftime('%Y-%m-%d'))

@bp.route('/payment/<int:id>/delete', methods=['POST'])
@login_required
def delete_payment(id):
    payment = Payment.query.get_or_404(id)
    
    # If it's linked to an invoice, subtract the amount
    if payment.invoice_id:
        sale = Sale.query.get(payment.invoice_id)
        if sale:
            sale.paid_amount -= payment.amount
            if sale.paid_amount < 0:
                sale.paid_amount = 0
            sale.update_status()
            
    # Also delete any mapped transaction for this payment
    # We search by reference_type and ID
    associated_txns = Transaction.query.filter_by(reference_type='payment', reference_id=payment.id).all()
    # Or if it was a sale/expense payment, find by those refs
    if payment.invoice_id:
        associated_txns += Transaction.query.filter_by(reference_type='sale', reference_id=payment.invoice_id, amount=payment.amount).all()
    elif payment.expense_id:
        associated_txns += Transaction.query.filter_by(reference_type='expense', reference_id=payment.expense_id, amount=payment.amount).all()
        
    for txn in associated_txns:
        db.session.delete(txn)
        
    try:
        db.session.delete(payment)
        db.session.commit()
        flash('Payment deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting payment: {str(e)}', 'error')
        
    return redirect(request.referrer or url_for('accounting.payments'))

@bp.route('/trial-balance')
def trial_balance():
    as_of_date = request.args.get('as_of_date', datetime.now().strftime('%Y-%m-%d'))
    as_of_datetime = datetime.strptime(as_of_date, '%Y-%m-%d')
    
    # Get all transactions up to date
    transactions = Transaction.query.filter(Transaction.date <= as_of_datetime).all()
    
    # Calculate balances per account
    account_balances = {}
    for t in transactions:
        if t.account not in account_balances:
            account_balances[t.account] = {'debit': 0, 'credit': 0}
        account_balances[t.account]['debit'] += t.debit
        account_balances[t.account]['credit'] += t.credit
    
    trial_balance_items = []
    total_debit = 0
    total_credit = 0
    
    for account, balances in account_balances.items():
        balance = balances['debit'] - balances['credit']
        if balance > 0:
            trial_balance_items.append({
                'account': account,
                'debit': balance,
                'credit': 0
            })
            total_debit += balance
        elif balance < 0:
            trial_balance_items.append({
                'account': account,
                'debit': 0,
                'credit': abs(balance)
            })
            total_credit += abs(balance)
    
    return render_template('accounting/trial_balance.html',
                         trial_balance=trial_balance_items,
                         total_debit=total_debit,
                         total_credit=total_credit,
                         as_of_date=as_of_date)

@bp.route('/profit-loss')
def profit_loss():
    start_date = request.args.get('start_date', 
                                  (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    
    start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
    end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
    
    # Sales revenue
    total_sales = db.session.query(func.sum(Sale.total)).filter(
        and_(Sale.date >= start_datetime, Sale.date <= end_datetime)
    ).scalar() or 0
    
    # Purchase costs
    total_purchases = db.session.query(func.sum(PurchaseBill.total)).filter(
        and_(PurchaseBill.date >= start_datetime, PurchaseBill.date <= end_datetime)
    ).scalar() or 0
    
    # Gross profit
    gross_profit = total_sales - total_purchases
    
    # Calculate operating expenses (you can add more expense accounts)
    expenses = {
        'Salaries': 0,
        'Rent': 0,
        'Utilities': 0,
        'Marketing': 0,
        'Other': 0
    }
    
    total_expenses = sum(expenses.values())
    net_profit = gross_profit - total_expenses
    
    return render_template('accounting/profit_loss.html',
                         total_sales=total_sales,
                         total_purchases=total_purchases,
                         gross_profit=gross_profit,
                         expenses=expenses,
                         total_expenses=total_expenses,
                         net_profit=net_profit,
                         start_date=start_date,
                         end_date=end_date)

@bp.route('/expenses')
@login_required
def expenses():
    # Get filter parameters
    vendor_id = request.args.get('vendor_id', type=int)
    category_id = request.args.get('category_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Build query
    query = Expense.query
    
    if vendor_id:
        query = query.filter(Expense.vendor_id == vendor_id)
    if category_id:
        query = query.filter(Expense.category_id == category_id)
    if start_date:
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Expense.date >= start_datetime)
    if end_date:
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        # Add one day to include the end date fully
        end_datetime = end_datetime + timedelta(days=1)
        query = query.filter(Expense.date < end_datetime)
    
    expenses = query.order_by(Expense.date.desc()).all()
    total_expense = sum(e.amount for e in expenses)
    
    # Get filter options
    categories = ExpenseCategory.query.filter_by(is_active=True).order_by(ExpenseCategory.name).all()
    vendors = Vendor.query.filter_by(is_active=True).order_by(Vendor.name).all()
    
    return render_template('accounting/expenses.html', 
                         expenses=expenses, 
                         total_expense=total_expense,
                         categories=categories,
                         vendors=vendors,
                         selected_vendor=vendor_id,
                         selected_category=category_id,
                         selected_start_date=start_date,
                         selected_end_date=end_date)

@bp.route('/expense/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    from app.models import ExpenseCategory, Vendor
    from werkzeug.utils import secure_filename
    import os
    
    form = ExpenseForm()
    
    # Populate category choices
    categories = ExpenseCategory.query.filter_by(is_active=True).order_by(ExpenseCategory.name).all()
    form.category_id.choices = [(cat.id, cat.name) for cat in categories]
    
    # Populate vendor choices
    vendors = Vendor.query.filter_by(is_active=True).order_by(Vendor.name).all()
    form.vendor_id.choices = [(0, 'Select Vendor (Optional)')] + [(v.id, v.name) for v in vendors]
    
    # Populate manufactured product choices (if column exists)
    from app.models import Product
    if has_column('products', 'is_manufactured'):
        manufactured_products = Product.query.filter_by(is_manufactured=True, is_active=True).order_by(Product.name).all()
    else:
        manufactured_products = []
    form.product_id.choices = [(0, 'Select Finished Product (Optional)')] + [(p.id, p.name) for p in manufactured_products]
    
    if form.validate_on_submit():
        expense_number = f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Build expense kwargs based on column existence
        expense_kwargs = {
            'expense_number': expense_number,
            'date': form.date.data,
            'category_id': form.category_id.data,
            'vendor_id': form.vendor_id.data if form.vendor_id.data != 0 else None,
            'description': form.description.data,
            'amount': form.amount.data,
            'payment_method': form.payment_method.data,
            'reference': form.reference.data,
            'notes': form.notes.data,
        }
        
        if has_column('expenses', 'is_bom_overhead'):
            expense_kwargs['is_bom_overhead'] = form.is_bom_overhead.data
        if has_column('expenses', 'product_id'):
            expense_kwargs['product_id'] = form.product_id.data if form.product_id.data != 0 else None
        
        expense = Expense(**expense_kwargs)
        
        # Handle bill image upload
        if 'bill_image' in request.files:
            bill_file = request.files['bill_image']
            if bill_file and bill_file.filename:
                filename = secure_filename(bill_file.filename)
                bill_path = os.path.join('app', 'static', 'uploads', 'bills', filename)
                os.makedirs(os.path.dirname(bill_path), exist_ok=True)
                bill_file.save(bill_path)
                # Normalize path to use forward slashes for consistency
                expense.bill_image_path = bill_path.replace('\\', '/')
        
        db.session.add(expense)
        db.session.commit()
        flash('Expense added successfully', 'success')
        return redirect(url_for('accounting.expenses'))
    
    return render_template('accounting/add_expense.html', form=form)

@bp.route('/expense/<int:id>/delete', methods=['POST'])
@login_required
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense removed', 'success')
    return redirect(url_for('accounting.expenses'))

@bp.route('/expense/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_expense(id):
    from app.models import ExpenseCategory, Vendor
    from werkzeug.utils import secure_filename
    import os
    
    expense = Expense.query.get_or_404(id)
    form = ExpenseForm(obj=expense)
    
    # Populate category choices
    categories = ExpenseCategory.query.filter_by(is_active=True).order_by(ExpenseCategory.name).all()
    form.category_id.choices = [(cat.id, cat.name) for cat in categories]
    
    # Populate vendor choices
    vendors = Vendor.query.filter_by(is_active=True).order_by(Vendor.name).all()
    form.vendor_id.choices = [(0, 'Select Vendor (Optional)')] + [(v.id, v.name) for v in vendors]
    
    # Populate manufactured product choices (if column exists)
    from app.models import Product
    if has_column('products', 'is_manufactured'):
        manufactured_products = Product.query.filter_by(is_manufactured=True, is_active=True).order_by(Product.name).all()
    else:
        manufactured_products = []
    form.product_id.choices = [(0, 'Select Finished Product (Optional)')] + [(p.id, p.name) for p in manufactured_products]
    
    # Set current vendor selection
    if expense.vendor_id:
        form.vendor_id.data = expense.vendor_id
    else:
        form.vendor_id.data = 0
        
    # Set current product selection (only if column exists)
    if has_column('expenses', 'product_id') and expense.product_id:
        form.product_id.data = expense.product_id
    else:
        form.product_id.data = 0
    
    if form.validate_on_submit():
        expense.date = form.date.data
        expense.category_id = form.category_id.data
        expense.vendor_id = form.vendor_id.data if form.vendor_id.data != 0 else None
        expense.description = form.description.data
        expense.amount = form.amount.data
        expense.payment_method = form.payment_method.data
        expense.reference = form.reference.data
        expense.notes = form.notes.data
        
        if has_column('expenses', 'is_bom_overhead'):
            expense.is_bom_overhead = form.is_bom_overhead.data
        if has_column('expenses', 'product_id'):
            expense.product_id = form.product_id.data if form.product_id.data != 0 else None
        
        # Handle bill image upload
        if 'bill_image' in request.files:
            bill_file = request.files['bill_image']
            if bill_file and bill_file.filename:
                filename = secure_filename(bill_file.filename)
                bill_path = os.path.join('app', 'static', 'uploads', 'bills', filename)
                os.makedirs(os.path.dirname(bill_path), exist_ok=True)
                bill_file.save(bill_path)
                # Normalize path to use forward slashes for consistency
                expense.bill_image_path = bill_path.replace('\\', '/')
        
        db.session.commit()
        flash('Expense updated successfully', 'success')
        return redirect(url_for('accounting.expenses'))
    
    return render_template('accounting/edit_expense.html', form=form, expense=expense)

@bp.route('/expense-categories')
@login_required
def expense_categories():
    from app.models import ExpenseCategory
    categories = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    return render_template('accounting/expense_categories.html', categories=categories)

@bp.route('/expense-category/add', methods=['GET', 'POST'])
@login_required
def add_expense_category():
    from app.models import ExpenseCategory
    from app.forms import ExpenseCategoryForm
    
    form = ExpenseCategoryForm()
    if form.validate_on_submit():
        category = ExpenseCategory(
            name=form.name.data,
            description=form.description.data
        )
        db.session.add(category)
        db.session.commit()
        flash('Expense category added successfully', 'success')
        return redirect(url_for('accounting.expense_categories'))
    
    return render_template('accounting/add_expense_category.html', form=form)

@bp.route('/expense-category/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_expense_category(id):
    from app.models import ExpenseCategory
    from app.forms import ExpenseCategoryForm
    
    category = ExpenseCategory.query.get_or_404(id)
    form = ExpenseCategoryForm(obj=category)
    
    if form.validate_on_submit():
        category.name = form.name.data
        category.description = form.description.data
        db.session.commit()
        flash('Expense category updated successfully', 'success')
        return redirect(url_for('accounting.expense_categories'))
    
    return render_template('accounting/edit_expense_category.html', form=form, category=category)

@bp.route('/expense-category/<int:id>/delete', methods=['POST'])
@login_required
def delete_expense_category(id):
    from app.models import ExpenseCategory
    
    category = ExpenseCategory.query.get_or_404(id)
    # Check if category is being used
    if category.expenses:
        flash('Cannot delete category that has expenses associated with it', 'error')
        return redirect(url_for('accounting.expense_categories'))
    
    db.session.delete(category)
    db.session.commit()
    flash('Expense category deleted successfully', 'success')
    return redirect(url_for('accounting.expense_categories'))