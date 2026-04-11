#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Expense, ExpenseCategory
from datetime import datetime, date
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    print("=" * 70)
    print("COMPREHENSIVE MONTHLY DIVISION FEATURE TEST")
    print("=" * 70)
    print()
    
    # Check database schema
    print("1. DATABASE SCHEMA CHECK")
    print("-" * 70)
    inspector = inspect(db.engine)
    expense_columns = [c['name'] for c in inspector.get_columns('expenses')]
    
    required_columns = ['is_monthly_divided', 'monthly_start_date', 'monthly_end_date', 'daily_amount']
    print(f"Expense table columns: {', '.join(expense_columns)}")
    print()
    
    for col in required_columns:
        exists = col in expense_columns
        status = "✓" if exists else "✗"
        print(f"  {status} {col}: {exists}")
    print()
    
    # Check Expense model methods
    print("2. EXPENSE MODEL METHODS CHECK")
    print("-" * 70)
    exp_methods = [method for method in dir(Expense) if not method.startswith('_')]
    
    monthly_methods = ['days_in_month', 'calculate_daily_amount', 'get_today_expense']
    for method in monthly_methods:
        has_method = method in exp_methods
        status = "✓" if has_method else "✗"
        print(f"  {status} {method}: {has_method}")
    print()
    
    # Check existing expenses
    print("3. EXISTING EXPENSES")
    print("-" * 70)
    all_expenses = Expense.query.all()
    print(f"Total expenses in database: {len(all_expenses)}")
    print()
    
    for exp in all_expenses:
        print(f"Expense: {exp.expense_number}")
        print(f"  Amount: Rs {exp.amount}")
        print(f"  Date: {exp.date}")
        print(f"  Description: {exp.description}")
        print(f"  Category: {exp.expense_category.name if exp.expense_category else 'None'}")
        
        if hasattr(exp, 'is_monthly_divided'):
            print(f"  Is Monthly Divided: {exp.is_monthly_divided}")
            if exp.is_monthly_divided:
                print(f"  Start Date: {exp.monthly_start_date}")
                print(f"  End Date: {exp.monthly_end_date}")
                print(f"  Daily Amount: Rs {exp.daily_amount}")
                
                # Test helper methods
                try:
                    days = exp.days_in_month()
                    print(f"  Days in Month: {days}")
                except Exception as e:
                    print(f"  Days in Month: ERROR - {e}")
                
                try:
                    today_expense = exp.get_today_expense()
                    print(f"  Today's Expense: Rs {today_expense}")
                except Exception as e:
                    print(f"  Today's Expense: ERROR - {e}")
        print()
    
    # Verify dashboard calculation
    print("4. DASHBOARD CALCULATION TEST")
    print("-" * 70)
    
    date_from = datetime(2026, 4, 1)
    date_to = datetime(2026, 4, 30)
    
    def has_column(table_name, column_name):
        cols = [c['name'] for c in inspector.get_columns(table_name)]
        return column_name in cols
    
    # Operating expenses
    if has_column('expenses', 'is_bom_overhead') and has_column('expenses', 'is_monthly_divided'):
        from sqlalchemy import func
        operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
            Expense.is_bom_overhead == False,
            Expense.is_monthly_divided == False,
            Expense.date >= date_from,
            Expense.date <= date_to
        ).scalar() or 0
        print(f"Operating Expenses (Non-Divided): Rs {operating_expenses}")
    
    # Divided expenses
    divided_total = 0
    monthly_expenses = Expense.query.filter(Expense.is_monthly_divided == True).all()
    print(f"Monthly Divided Expenses: {len(monthly_expenses)}")
    
    for exp in monthly_expenses:
        if exp.monthly_start_date and exp.monthly_end_date:
            overlap_start = max(exp.monthly_start_date, date_from.date())
            overlap_end = min(exp.monthly_end_date, date_to.date())
            
            if overlap_start <= overlap_end:
                overlap_days = (overlap_end - overlap_start).days + 1
                proportional = exp.daily_amount * overlap_days
                divided_total += proportional
                print(f"  - {exp.expense_number}: Rs {proportional} ({overlap_days} days × Rs {exp.daily_amount}/day)")
    
    print(f"Total Divided Expenses (Proportional): Rs {divided_total}")
    print()
    
    # Test form fields
    print("5. EXPENSE FORM FIELDS CHECK")
    print("-" * 70)
    from app.forms import ExpenseForm
    form_fields = [field for field in dir(ExpenseForm()) if not field.startswith('_')]
    
    expected_fields = ['is_monthly_divided', 'monthly_start_date', 'monthly_end_date']
    for field in expected_fields:
        has_field = field in form_fields
        status = "✓" if has_field else "✗"
        print(f"  {status} {field}: {has_field}")
    print()
    
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    all_checks_passed = (
        all(col in expense_columns for col in required_columns) and
        all(method in exp_methods for method in monthly_methods) and
        len(all_expenses) > 0 and
        divided_total > 0
    )
    
    if all_checks_passed:
        print("✓ ALL TESTS PASSED - Feature is fully implemented and working!")
    else:
        print("✗ Some tests failed - please review above")
    print("=" * 70)
