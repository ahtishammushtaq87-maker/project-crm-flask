#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Expense

app = create_app()
with app.app_context():
    print("\n" + "=" * 80)
    print("CHECKING ALL EXPENSES IN DATABASE")
    print("=" * 80 + "\n")
    
    all_expenses = Expense.query.all()
    
    for i, exp in enumerate(all_expenses, 1):
        print(f"{i}. {exp.expense_number}")
        print(f"   Amount: Rs {exp.amount}")
        print(f"   Date: {exp.date.date()}")
        print(f"   is_monthly_divided: {exp.is_monthly_divided}")
        print(f"   is_bom_overhead: {exp.is_bom_overhead}")
        if exp.is_monthly_divided:
            print(f"   Period: {exp.monthly_start_date} to {exp.monthly_end_date}")
            print(f"   Daily: Rs {exp.daily_amount}")
        print()
    
    print("=" * 80)
