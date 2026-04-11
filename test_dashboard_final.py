#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Expense, Sale, SaleItem, Product, PurchaseBill, ExpenseCategory
from datetime import datetime, timedelta
from sqlalchemy import func

app = create_app()
with app.app_context():
    # Test date range (April 2026)
    date_from = datetime(2026, 4, 1)
    date_to = datetime(2026, 4, 30)
    
    print("=" * 60)
    print("DASHBOARD CALCULATION TEST")
    print("=" * 60)
    print(f"Date Range: {date_from.date()} to {date_to.date()}")
    print()
    
    # Check if columns exist
    def has_column(table_name, column_name):
        inspector = db.inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns(table_name)]
        return column_name in columns
    
    print("Column Check:")
    print(f"  - is_monthly_divided: {has_column('expenses', 'is_monthly_divided')}")
    print(f"  - is_bom_overhead: {has_column('expenses', 'is_bom_overhead')}")
    print()
    
    # Get all expenses
    all_expenses = Expense.query.all()
    print(f"Total Expenses in DB: {len(all_expenses)}")
    for exp in all_expenses:
        print(f"  - {exp.expense_number}: Rs {exp.amount}")
        if has_column('expenses', 'is_monthly_divided'):
            print(f"    Divided: {exp.is_monthly_divided}")
            if exp.is_monthly_divided:
                print(f"    Period: {exp.monthly_start_date} to {exp.monthly_end_date}")
                print(f"    Daily: Rs {exp.daily_amount}")
    print()
    
    # Calculate operating expenses
    if has_column('expenses', 'is_bom_overhead'):
        if has_column('expenses', 'is_monthly_divided'):
            operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.is_bom_overhead == False,
                Expense.is_monthly_divided == False,
                Expense.date >= date_from,
                Expense.date <= date_to
            ).scalar() or 0
        else:
            operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.is_bom_overhead == False,
                Expense.date >= date_from,
                Expense.date <= date_to
            ).scalar() or 0
    else:
        operating_expenses = 0
    
    print(f"Operating Expenses (Non-Divided): Rs {operating_expenses}")
    print()
    
    # Calculate divided expenses for period
    divided_expenses_for_period = 0
    if has_column('expenses', 'is_monthly_divided'):
        all_monthly_expenses = Expense.query.filter(
            Expense.is_monthly_divided == True
        ).all()
        
        print(f"Monthly Divided Expenses Found: {len(all_monthly_expenses)}")
        for exp in all_monthly_expenses:
            if exp.monthly_start_date and exp.monthly_end_date:
                overlap_start = max(exp.monthly_start_date, date_from.date())
                overlap_end = min(exp.monthly_end_date, date_to.date())
                
                if overlap_start <= overlap_end:
                    overlap_days = (overlap_end - overlap_start).days + 1
                    proportional_amount = exp.daily_amount * overlap_days
                    divided_expenses_for_period += proportional_amount
                    
                    print(f"  - {exp.expense_number}:")
                    print(f"    Period: {exp.monthly_start_date} to {exp.monthly_end_date}")
                    print(f"    Daily Amount: Rs {exp.daily_amount}")
                    print(f"    Overlap: {overlap_start} to {overlap_end}")
                    print(f"    Overlap Days: {overlap_days}")
                    print(f"    Proportional: Rs {proportional_amount}")
    
    print()
    print(f"Total Divided Expenses (Proportional): Rs {divided_expenses_for_period}")
    print()
    print(f"TOTAL EXPENSES: Rs {operating_expenses + divided_expenses_for_period}")
    print("=" * 60)
