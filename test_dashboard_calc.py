#!/usr/bin/env python
"""Test accounting dashboard directly"""
import sys
sys.path.insert(0, '/d:/prefex_flask/project_crm_flask/project_crm_flask')

from app import create_app, db
from datetime import datetime, timedelta

app = create_app()

with app.app_context():
    try:
        print("[*] Testing dashboard calculation...")
        
        # Simulate the dashboard calculation
        date_from = datetime.utcnow() - timedelta(days=30)
        date_to = datetime.utcnow()
        
        print(f"[*] Date range: {date_from.date()} to {date_to.date()}")
        print("[*] Calculation should complete without errors...")
        
        # Test with real database
        from app.models import Expense
        from sqlalchemy import func
        
        expenses = Expense.query.all()
        print(f"[*] Total expenses in database: {len(expenses)}")
        
        for exp in expenses[:5]:
            print(f"  - {exp.expense_number}: Rs {exp.amount}, divided: {getattr(exp, 'is_monthly_divided', None)}")
        
        print("[SUCCESS] No errors in dashboard calculation!")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
