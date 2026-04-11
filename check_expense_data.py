#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Expense

app = create_app()
with app.app_context():
    print("=" * 70)
    print("CHECKING EXPENSE FIELDS IN DATABASE")
    print("=" * 70)
    print()
    
    # Get the actual row data
    all_expenses = Expense.query.all()
    
    for exp in all_expenses:
        print(f"Expense: {exp.expense_number}")
        print(f"  ID: {exp.id}")
        print(f"  Amount: {exp.amount}")
        print(f"  is_bom_overhead: {exp.is_bom_overhead} (type: {type(exp.is_bom_overhead)}, repr: {repr(exp.is_bom_overhead)})")
        print(f"  is_monthly_divided: {exp.is_monthly_divided} (type: {type(exp.is_monthly_divided)}, repr: {repr(exp.is_monthly_divided)})")
        print(f"  monthly_start_date: {exp.monthly_start_date}")
        print(f"  monthly_end_date: {exp.monthly_end_date}")
        print(f"  daily_amount: {exp.daily_amount}")
        print()
    
    # Now test the filter
    print("=" * 70)
    print("TESTING FILTER CONDITIONS")
    print("=" * 70)
    print()
    
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    today = datetime(2026, 4, 9)
    date_from = today - timedelta(days=30)
    date_to = today
    
    print(f"Filter: is_bom_overhead=False, is_monthly_divided=False, date >= {date_from.date()}, date <= {date_to.date()}")
    print()
    
    # Direct raw SQL query
    result = db.session.execute(
        db.text("""
            SELECT id, expense_number, amount, is_bom_overhead, is_monthly_divided, date 
            FROM expenses 
            WHERE is_bom_overhead = 0 
              AND is_monthly_divided = 0 
              AND date >= :date_from 
              AND date <= :date_to
        """),
        {"date_from": date_from, "date_to": date_to}
    )
    
    rows = result.fetchall()
    print(f"Raw SQL Results: {len(rows)} rows")
    for row in rows:
        print(f"  {row}")
    print()
    
    # Test with ORM filter
    orm_results = Expense.query.filter(
        Expense.is_bom_overhead == False,
        Expense.is_monthly_divided == False,
        Expense.date >= date_from,
        Expense.date <= date_to
    ).all()
    
    print(f"ORM Filter Results: {len(orm_results)} rows")
    for exp in orm_results:
        print(f"  {exp.expense_number}: Rs {exp.amount}")
    print()
    
    # Test individual conditions
    print("Testing individual conditions:")
    print(f"  is_bom_overhead == False: {Expense.query.filter(Expense.is_bom_overhead == False).count()} rows")
    print(f"  is_monthly_divided == False: {Expense.query.filter(Expense.is_monthly_divided == False).count()} rows")
    print(f"  is_monthly_divided == True: {Expense.query.filter(Expense.is_monthly_divided == True).count()} rows")
    print(f"  date in range: {Expense.query.filter(Expense.date >= date_from, Expense.date <= date_to).count()} rows")
