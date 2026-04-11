#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Expense
from datetime import datetime, timedelta
from sqlalchemy import func, inspect

app = create_app()
with app.app_context():
    print("=" * 70)
    print("DEBUGGING DASHBOARD EXPENSE CALCULATION")
    print("=" * 70)
    print()
    
    # Simulate dashboard date range (last 30 days from April 9, 2026)
    today = datetime(2026, 4, 9)
    date_from = today - timedelta(days=30)
    date_to = today
    
    print(f"Dashboard Date Range: {date_from.date()} to {date_to.date()}")
    print()
    
    # Check database columns
    inspector = inspect(db.engine)
    expense_columns = [c['name'] for c in inspector.get_columns('expenses')]
    has_bom = 'is_bom_overhead' in expense_columns
    has_divided = 'is_monthly_divided' in expense_columns
    
    print(f"Column Check: is_bom_overhead={has_bom}, is_monthly_divided={has_divided}")
    print()
    
    # Get all expenses
    all_expenses = Expense.query.all()
    print(f"Total Expenses: {len(all_expenses)}")
    for exp in all_expenses:
        print(f"  - {exp.expense_number}: Rs {exp.amount}, Date: {exp.date.date()}, Divided: {exp.is_monthly_divided}, BOM: {exp.is_bom_overhead}")
    print()
    
    # Test the actual query used in dashboard
    print("DASHBOARD QUERIES:")
    print("-" * 70)
    
    # Operating expenses query
    print("1. Operating Expenses (is_bom_overhead=False, is_monthly_divided=False):")
    operating_query = db.session.query(Expense).filter(
        Expense.is_bom_overhead == False,
        Expense.is_monthly_divided == False,
        Expense.date >= date_from,
        Expense.date <= date_to
    )
    operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.is_bom_overhead == False,
        Expense.is_monthly_divided == False,
        Expense.date >= date_from,
        Expense.date <= date_to
    ).scalar() or 0
    
    print(f"   SQL: {operating_query}")
    print(f"   Results: {operating_query.all()}")
    print(f"   Total: Rs {operating_expenses}")
    print()
    
    # BOM expenses query
    print("2. Manufacturing Overhead (is_bom_overhead=True, is_monthly_divided=False):")
    bom_query = db.session.query(Expense).filter(
        Expense.is_bom_overhead == True,
        Expense.is_monthly_divided == False,
        Expense.date >= date_from,
        Expense.date <= date_to
    )
    manufacturing_overhead = db.session.query(func.sum(Expense.amount)).filter(
        Expense.is_bom_overhead == True,
        Expense.is_monthly_divided == False,
        Expense.date >= date_from,
        Expense.date <= date_to
    ).scalar() or 0
    
    print(f"   Results: {bom_query.all()}")
    print(f"   Total: Rs {manufacturing_overhead}")
    print()
    
    # Divided expenses
    print("3. Divided Expenses (is_monthly_divided=True):")
    divided_query = db.session.query(Expense).filter(
        Expense.is_monthly_divided == True
    )
    print(f"   Results: {divided_query.all()}")
    print()
    
    # Calculate proportional
    print("4. Proportional Calculation:")
    divided_expenses_for_period = 0
    for exp in divided_query.all():
        if exp.monthly_start_date and exp.monthly_end_date:
            overlap_start = max(exp.monthly_start_date, date_from.date())
            overlap_end = min(exp.monthly_end_date, date_to.date())
            
            if overlap_start <= overlap_end:
                overlap_days = (overlap_end - overlap_start).days + 1
                proportional = exp.daily_amount * overlap_days
                divided_expenses_for_period += proportional
                print(f"   {exp.expense_number}:")
                print(f"     Period: {exp.monthly_start_date} to {exp.monthly_end_date}")
                print(f"     Overlap: {overlap_start} to {overlap_end} ({overlap_days} days)")
                print(f"     Daily: Rs {exp.daily_amount} × {overlap_days} = Rs {proportional}")
    
    print(f"   Total Divided: Rs {divided_expenses_for_period}")
    print()
    
    # Final totals
    print("=" * 70)
    print("DASHBOARD TOTALS:")
    print(f"  Operating Expenses: Rs {operating_expenses}")
    print(f"  Manufacturing Overhead: Rs {manufacturing_overhead}")
    print(f"  Divided Expenses (Proportional): Rs {divided_expenses_for_period}")
    print(f"  TOTAL EXPENSES: Rs {operating_expenses + manufacturing_overhead + divided_expenses_for_period}")
    print("=" * 70)
