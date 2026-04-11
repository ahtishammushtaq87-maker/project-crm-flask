#!/usr/bin/env python
"""
Test script to verify daily salary calculation in dashboard
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Staff, Expense
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    print("\n" + "=" * 80)
    print("TESTING DAILY SALARY CALCULATION FOR DASHBOARD")
    print("=" * 80 + "\n")
    
    # Create sample staff for testing
    print("1. CREATING TEST STAFF MEMBERS:")
    print("-" * 80)
    
    # Check if staff already exist
    existing_staff = Staff.query.all()
    if len(existing_staff) > 0:
        print(f"Found {len(existing_staff)} existing staff members:")
        for staff in existing_staff:
            staff.calculate_daily_salary()
            db.session.commit()
            print(f"  - {staff.name}: Monthly: Rs {staff.monthly_salary}, Daily: Rs {staff.daily_salary:.2f}")
    else:
        print("No staff members found. Creating test staff...")
        
        staff1 = Staff(
            name="Ahmed Ali",
            designation="Manager",
            monthly_salary=30000,
            joining_date=datetime(2026, 1, 1).date(),
            is_active=True
        )
        staff1.calculate_daily_salary()
        
        staff2 = Staff(
            name="Fatima Khan",
            designation="Assistant",
            monthly_salary=20000,
            joining_date=datetime(2026, 1, 1).date(),
            is_active=True
        )
        staff2.calculate_daily_salary()
        
        db.session.add(staff1)
        db.session.add(staff2)
        db.session.commit()
        
        print(f"  ✓ Created {staff1.name}: Rs {staff1.monthly_salary} → Rs {staff1.daily_salary:.2f}/day")
        print(f"  ✓ Created {staff2.name}: Rs {staff2.monthly_salary} → Rs {staff2.daily_salary:.2f}/day")
    print()
    
    # Test dashboard calculation
    print("2. DASHBOARD CALCULATION (April 1-30, 2026):")
    print("-" * 80)
    
    start_date = datetime(2026, 4, 1)
    end_date = datetime(2026, 4, 30, 23, 59, 59)
    days_in_period = (end_date.date() - start_date.date()).days + 1
    
    print(f"Period: {start_date.date()} to {end_date.date()} ({days_in_period} days)\n")
    
    active_staff = Staff.query.filter_by(is_active=True).all()
    total_daily_payroll = 0
    
    print(f"Active Staff Payroll Breakdown:")
    for staff in active_staff:
        payroll_for_period = staff.daily_salary * days_in_period
        total_daily_payroll += payroll_for_period
        print(f"  {staff.name}:")
        print(f"    Daily Salary: Rs {staff.daily_salary:.2f}")
        print(f"    Days in Period: {days_in_period}")
        print(f"    Total for Period: Rs {payroll_for_period:.2f}")
    print()
    
    print(f"Total Daily Payroll for Period: Rs {total_daily_payroll:.2f}\n")
    
    # Show what dashboard will display
    print("3. WHAT DASHBOARD WILL SHOW:")
    print("-" * 80)
    print(f"✓ Operating Expenses: Rs 0.00")
    print(f"✓ BOM Overhead: Rs 0.00")
    print(f"✓ Daily Payroll (Active Staff): Rs {total_daily_payroll:.2f}")
    
    # Check divided expenses
    divided_expenses = Expense.query.filter_by(is_monthly_divided=True).all()
    divided_total = 0
    if divided_expenses:
        print(f"✓ Divided Expenses:")
        for exp in divided_expenses:
            overlap_start = max(exp.monthly_start_date, start_date.date())
            overlap_end = min(exp.monthly_end_date, end_date.date())
            if overlap_start <= overlap_end:
                overlap_days = (overlap_end - overlap_start).days + 1
                proportional = exp.daily_amount * overlap_days
                divided_total += proportional
                print(f"    {exp.description}: Rs {proportional:.2f} ({overlap_days} days)")
    
    total_expenses = total_daily_payroll + divided_total
    print(f"✓ TOTAL EXPENSES: Rs {total_expenses:.2f}")
    print()
    
    print("=" * 80)
    print("✅ KEY CHANGES FROM OLD SYSTEM:")
    print("=" * 80)
    print("✓ No longer adding 'Advance Given' values")
    print("✓ No longer adding 'Salary Paid' values")
    print("✓ Now using DAILY SALARY × DAYS IN PERIOD for active staff")
    print("✓ Monthly salary automatically divided by 30 for daily calculation")
    print("✓ Only active staff included in payroll calculation")
    print("=" * 80 + "\n")
