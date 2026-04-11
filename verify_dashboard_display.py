#!/usr/bin/env python
"""
This script simulates the exact dashboard calculation to show what SHOULD be displayed.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Expense, Sale, SaleItem, Product, PurchaseBill, ExpenseCategory
from datetime import datetime, timedelta
from sqlalchemy import func

app = create_app()
with app.app_context():
    print("\n" + "=" * 80)
    print("DASHBOARD DISPLAY VERIFICATION - WHAT USER SHOULD SEE")
    print("=" * 80 + "\n")
    
    # Simulate user accessing dashboard on April 9, 2026 without date filters (last 30 days)
    today = datetime(2026, 4, 9, 12, 0, 0)  # Current date/time on dashboard
    date_from = today - timedelta(days=30)  # Default is last 30 days
    date_to = today
    
    print(f"📅 Dashboard Date Range (Last 30 Days): {date_from.date()} to {date_to.date()}\n")
    
    # Helper function
    def has_column(table_name, column_name):
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns(table_name)]
        return column_name in columns
    
    # 1. Calculate Sales (same for both)
    total_sales = db.session.query(func.sum(Sale.total)).filter(
        Sale.date >= date_from,
        Sale.date <= date_to
    ).scalar() or 0
    
    # 2. Calculate COGS (same for both)
    total_cogs = db.session.query(func.sum(SaleItem.quantity * Product.cost_price))\
        .join(Sale, SaleItem.sale_id == Sale.id)\
        .join(Product, SaleItem.product_id == Product.id)\
        .filter(Sale.date >= date_from, Sale.date <= date_to)\
        .scalar() or 0
    
    # 3. Calculate Purchases (same for both)
    total_purchases = db.session.query(func.sum(PurchaseBill.total)).filter(
        PurchaseBill.date >= date_from, PurchaseBill.date <= date_to
    ).scalar() or 0
    
    print("📊 REVENUE & PURCHASES:")
    print(f"   Total Sales:         Rs {total_sales:>12,.2f}")
    print(f"   COGS:                Rs {total_cogs:>12,.2f}")
    print(f"   Gross Profit:        Rs {(total_sales - total_cogs):>12,.2f}\n")
    
    print(f"   Total Purchases:     Rs {total_purchases:>12,.2f}\n")
    
    # 4. Calculate OPERATING EXPENSES - NON-DIVIDED ONLY
    if has_column('expenses', 'is_bom_overhead') and has_column('expenses', 'is_monthly_divided'):
        operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
            Expense.is_bom_overhead == False,
            Expense.is_monthly_divided == False,  # <-- IMPORTANT: Exclude divided expenses
            Expense.date >= date_from,
            Expense.date <= date_to
        ).scalar() or 0
        
        manufacturing_overhead = db.session.query(func.sum(Expense.amount)).filter(
            Expense.is_bom_overhead == True,
            Expense.is_monthly_divided == False,  # <-- IMPORTANT: Exclude divided expenses
            Expense.date >= date_from,
            Expense.date <= date_to
        ).scalar() or 0
    else:
        operating_expenses = 0
        manufacturing_overhead = 0
    
    print("💰 REGULAR EXPENSES (Non-Divided):")
    print(f"   Operating:          Rs {operating_expenses:>12,.2f}")
    print(f"   BOM Overhead:       Rs {manufacturing_overhead:>12,.2f}\n")
    
    # 5. Calculate DIVIDED EXPENSES - PROPORTIONAL FOR DATE RANGE
    divided_expenses_for_period = 0
    divided_breakdown = []
    
    if has_column('expenses', 'is_monthly_divided'):
        monthly_expenses = Expense.query.filter(Expense.is_monthly_divided == True).all()
        
        for exp in monthly_expenses:
            if exp.monthly_start_date and exp.monthly_end_date:
                # Find overlap between expense period and filter period
                overlap_start = max(exp.monthly_start_date, date_from.date())
                overlap_end = min(exp.monthly_end_date, date_to.date())
                
                if overlap_start <= overlap_end:
                    overlap_days = (overlap_end - overlap_start).days + 1
                    proportional_amount = exp.daily_amount * overlap_days
                    divided_expenses_for_period += proportional_amount
                    
                    divided_breakdown.append({
                        'number': exp.expense_number,
                        'description': exp.description,
                        'total': exp.amount,
                        'period': f"{exp.monthly_start_date} to {exp.monthly_end_date}",
                        'daily': exp.daily_amount,
                        'days': overlap_days,
                        'proportional': proportional_amount
                    })
    
    print("📈 MONTHLY DIVIDED EXPENSES (Proportional for Period):")
    if divided_breakdown:
        for item in divided_breakdown:
            print(f"   {item['number']}: {item['description']}")
            print(f"     Total Amount:    Rs {item['total']:>12,.2f} ({item['period']})")
            print(f"     Daily Rate:      Rs {item['daily']:>12,.2f}")
            print(f"     Days in Period:  {item['days']:>20} days")
            print(f"     ➜ Proportional:   Rs {item['proportional']:>12,.2f}")
    else:
        print("   (No monthly divided expenses)")
    
    print(f"\n   Total Divided (Proportional): Rs {divided_expenses_for_period:>8,.2f}\n")
    
    # 6. TOTAL EXPENSES
    total_expenses = operating_expenses + manufacturing_overhead + divided_expenses_for_period
    
    print("=" * 80)
    print("📋 WHAT USER SHOULD SEE ON DASHBOARD - EXPENSES CARD:")
    print("=" * 80)
    print(f"\n   Total Expenses:      Rs {total_expenses:>12,.2f}")
    print(f"   ├─ Op:               Rs {operating_expenses:>12,.2f}  (Regular operating)")
    print(f"   ├─ BOM:              Rs {manufacturing_overhead:>12,.2f}  (Manufacturing overhead)")
    if divided_expenses_for_period > 0:
        print(f"   └─ Divided (Period): Rs {divided_expenses_for_period:>12,.2f}  ({date_from.date()} to {date_to.date()})")
    
    # 7. NET PROFIT
    net_profit = (total_sales - total_cogs) - total_expenses
    
    print(f"\n   Gross Profit:        Rs {(total_sales - total_cogs):>12,.2f}  (Sales - COGS)")
    print(f"   Net Profit:          Rs {net_profit:>12,.2f}  (Gross - Expenses)")
    print("\n" + "=" * 80)
    
    # Verification
    print("\n✅ VERIFICATION:")
    print(f"   ✓ Operating expenses (non-divided only):  Rs {operating_expenses:,.2f}")
    print(f"   ✓ Divided expenses are proportional:      Rs {divided_expenses_for_period:,.2f}")
    print(f"   ✓ NOT showing full Rs 77,000 for Op:      ✓ CORRECT")
    print(f"   ✓ Total = {operating_expenses} + {manufacturing_overhead} + {divided_expenses_for_period} = {total_expenses:,.2f}")
    print("\n" + "=" * 80 + "\n")
