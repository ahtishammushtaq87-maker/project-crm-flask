#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Expense
from datetime import datetime
from sqlalchemy import func, inspect

app = create_app()
with app.app_context():
    print("=" * 80)
    print("DEBUG: TESTING WITH USER'S EXACT DATE RANGE (04/01/2026 to 04/09/2026)")
    print("=" * 80)
    print()
    
    # User's exact date range from screenshot
    date_from = datetime.strptime('04/01/2026', '%m/%d/%Y')
    date_to = datetime.strptime('04/09/2026', '%m/%d/%Y')
    
    print(f"Date Range: {date_from.date()} to {date_to.date()}\n")
    
    # Check columns
    inspector = inspect(db.engine)
    has_bom = 'is_bom_overhead' in [c['name'] for c in inspector.get_columns('expenses')]
    has_divided = 'is_monthly_divided' in [c['name'] for c in inspector.get_columns('expenses')]
    
    print(f"Columns: is_bom_overhead={has_bom}, is_monthly_divided={has_divided}\n")
    
    # Get all expenses
    all_exp = Expense.query.all()
    print(f"Total Expenses in DB: {len(all_exp)}")
    for exp in all_exp:
        print(f"  {exp.expense_number}: Rs {exp.amount}")
        print(f"    Divided: {exp.is_monthly_divided}, Date: {exp.date.date()}")
        print(f"    Period: {exp.monthly_start_date} to {exp.monthly_end_date}")
        print(f"    Daily: Rs {exp.daily_amount}\n")
    
    print("=" * 80)
    print("OPERATING EXPENSES QUERY (is_monthly_divided=False):")
    print("=" * 80)
    
    # Operating expenses
    operating = db.session.query(func.sum(Expense.amount)).filter(
        Expense.is_bom_overhead == False,
        Expense.is_monthly_divided == False,
        Expense.date >= date_from,
        Expense.date <= date_to
    ).scalar() or 0
    
    print(f"Result: Rs {operating}\n")
    
    # Check what WOULD match if we didn't filter
    all_in_range = db.session.query(Expense).filter(
        Expense.date >= date_from,
        Expense.date <= date_to
    ).all()
    
    print(f"All expenses in date range: {len(all_in_range)}")
    for exp in all_in_range:
        print(f"  {exp.expense_number}: Rs {exp.amount} (Divided: {exp.is_monthly_divided})\n")
    
    print("=" * 80)
    print("DIVIDED EXPENSES QUERY:")
    print("=" * 80)
    
    divided_all = Expense.query.filter(Expense.is_monthly_divided == True).all()
    print(f"Total divided expenses: {len(divided_all)}\n")
    
    divided_for_period = 0
    for exp in divided_all:
        if exp.monthly_start_date and exp.monthly_end_date:
            overlap_start = max(exp.monthly_start_date, date_from.date())
            overlap_end = min(exp.monthly_end_date, date_to.date())
            
            print(f"Expense: {exp.expense_number}")
            print(f"  Period: {exp.monthly_start_date} to {exp.monthly_end_date}")
            print(f"  Overlap: {overlap_start} to {overlap_end}")
            
            if overlap_start <= overlap_end:
                overlap_days = (overlap_end - overlap_start).days + 1
                proportional = exp.daily_amount * overlap_days
                divided_for_period += proportional
                print(f"  Days: {overlap_days}")
                print(f"  Daily: Rs {exp.daily_amount}")
                print(f"  Proportional: Rs {proportional}\n")
            else:
                print(f"  NO OVERLAP\n")
    
    print("=" * 80)
    print("TOTALS:")
    print("=" * 80)
    print(f"Operating Expenses: Rs {operating}")
    print(f"Divided For Period: Rs {divided_for_period}")
    print(f"TOTAL EXPENSES: Rs {operating + divided_for_period}")
    print("\n(If showing Rs 77,000, that's the bug!)")
    print("=" * 80)
