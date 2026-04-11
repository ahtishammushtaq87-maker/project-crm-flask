#!/usr/bin/env python
"""
Test script for professional attendance/time tracking system
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Staff, Attendance
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    print("\n" + "=" * 90)
    print("PROFESSIONAL ATTENDANCE & TIME TRACKING SYSTEM - TEST")
    print("=" * 90 + "\n")
    
    # Get staff member
    staff = Staff.query.first()
    if not staff:
        print("❌ No staff members found!")
        sys.exit(1)
    
    print(f"Staff Member: {staff.name}")
    print(f"Monthly Salary: Rs {staff.monthly_salary:,.2f}")
    print(f"Daily Salary (30 days): Rs {staff.daily_salary:,.2f}")
    print(f"Hourly Rate (8 hours/day): Rs {staff.daily_salary / 8:,.2f}/hour\n")
    
    # Create sample attendance records for testing
    print("-" * 90)
    print("CREATING TEST ATTENDANCE RECORDS")
    print("-" * 90 + "\n")
    
    today = datetime(2026, 4, 9)
    
    # Test Case 1: Normal 8-hour day
    att1 = Attendance(
        staff_id=staff.id,
        date=today.date(),
        clock_in=datetime(2026, 4, 9, 9, 0),
        clock_out=datetime(2026, 4, 9, 17, 0)
    )
    att1.staff = staff  # Ensure relationship is set
    att1.calculate_hours_worked()
    att1.calculate_earned_amount()
    db.session.add(att1)
    
    print(f"1️⃣  NORMAL DAY (9 AM - 5 PM)")
    print(f"   Clock In:  {att1.clock_in.strftime('%H:%M:%S')}")
    print(f"   Clock Out: {att1.clock_out.strftime('%H:%M:%S')}")
    print(f"   Duration:  {att1.get_time_summary()}")
    print(f"   Rate:      Rs {att1.hourly_rate:,.2f}/hour")
    print(f"   Earned:    Rs {att1.earned_amount:,.2f}\n")
    
    # Test Case 2: Half day (4 hours)
    att2 = Attendance(
        staff_id=staff.id,
        date=(today + timedelta(days=1)).date(),
        clock_in=datetime(2026, 4, 10, 9, 0),
        clock_out=datetime(2026, 4, 10, 13, 0)
    )
    att2.staff = staff  # Ensure relationship is set
    att2.calculate_hours_worked()
    att2.calculate_earned_amount()
    db.session.add(att2)
    
    print(f"2️⃣  HALF DAY (9 AM - 1 PM)")
    print(f"   Clock In:  {att2.clock_in.strftime('%H:%M:%S')}")
    print(f"   Clock Out: {att2.clock_out.strftime('%H:%M:%S')}")
    print(f"   Duration:  {att2.get_time_summary()}")
    print(f"   Rate:      Rs {att2.hourly_rate:,.2f}/hour")
    print(f"   Earned:    Rs {att2.earned_amount:,.2f}\n")
    
    # Test Case 3: Extra hours (10 hours)
    att3 = Attendance(
        staff_id=staff.id,
        date=(today + timedelta(days=2)).date(),
        clock_in=datetime(2026, 4, 11, 8, 0),
        clock_out=datetime(2026, 4, 11, 18, 0)
    )
    att3.staff = staff  # Ensure relationship is set
    att3.calculate_hours_worked()
    att3.calculate_earned_amount()
    db.session.add(att3)
    
    print(f"3️⃣  OVERTIME (8 AM - 6 PM)")
    print(f"   Clock In:  {att3.clock_in.strftime('%H:%M:%S')}")
    print(f"   Clock Out: {att3.clock_out.strftime('%H:%M:%S')}")
    print(f"   Duration:  {att3.get_time_summary()}")
    print(f"   Rate:      Rs {att3.hourly_rate:,.2f}/hour")
    print(f"   Earned:    Rs {att3.earned_amount:,.2f}\n")
    
    # Test Case 4: Partial hours (6h 30m)
    att4 = Attendance(
        staff_id=staff.id,
        date=(today + timedelta(days=3)).date(),
        clock_in=datetime(2026, 4, 12, 9, 0),
        clock_out=datetime(2026, 4, 12, 15, 30),
        notes="Left early for meeting"
    )
    att4.staff = staff  # Ensure relationship is set
    att4.calculate_hours_worked()
    att4.calculate_earned_amount()
    db.session.add(att4)
    
    print(f"4️⃣  PARTIAL DAY WITH MINUTES (9 AM - 3:30 PM)")
    print(f"   Clock In:  {att4.clock_in.strftime('%H:%M:%S')}")
    print(f"   Clock Out: {att4.clock_out.strftime('%H:%M:%S')}")
    print(f"   Duration:  {att4.get_time_summary()}")
    print(f"   Rate:      Rs {att4.hourly_rate:,.2f}/hour")
    print(f"   Earned:    Rs {att4.earned_amount:,.2f}")
    print(f"   Notes:     {att4.notes}\n")
    
    db.session.commit()
    
    # Summary
    print("-" * 90)
    print("PERIOD SUMMARY (April 9-12, 2026)")
    print("-" * 90 + "\n")
    
    period_start = today.date()
    period_end = (today + timedelta(days=3)).date()
    
    records = Attendance.query.filter(
        Attendance.date >= period_start,
        Attendance.date <= period_end,
        Attendance.staff_id == staff.id
    ).all()
    
    total_hours = sum(r.hours_worked for r in records)
    total_minutes = sum(r.minutes_worked for r in records)
    total_earned = sum(r.earned_amount for r in records)
    
    total_hours += total_minutes // 60
    total_minutes = total_minutes % 60
    
    print(f"📊 Period: {period_start} to {period_end}")
    print(f"📋 Total Records: {len(records)}")
    print(f"⏱️  Total Hours: {total_hours}h {total_minutes}m")
    print(f"💰 Total Earned: Rs {total_earned:,.2f}\n")
    
    print("-" * 90)
    print("DETAILED BREAKDOWN")
    print("-" * 90 + "\n")
    
    for i, record in enumerate(records, 1):
        print(f"Day {i} ({record.date}):")
        print(f"  Time:   {record.clock_in.strftime('%H:%M')} - {record.clock_out.strftime('%H:%M')} ({record.get_time_summary()})")
        print(f"  Earned: Rs {record.earned_amount:,.2f}")
        if record.notes:
            print(f"  Notes:  {record.notes}")
        print()
    
    print("=" * 90)
    print("✅ PROFESSIONAL ATTENDANCE SYSTEM - KEY FEATURES:")
    print("=" * 90)
    print("✓ Clock In/Out with timestamp tracking")
    print("✓ Automatic hours & minutes calculation")
    print("✓ Hourly rate calculated from monthly salary")
    print("✓ Automatic earned amount calculation")
    print("✓ Support for partial hours and minutes")
    print("✓ Notes field for special cases (leaves, overtime, etc.)")
    print("✓ Date range filtering for dashboard")
    print("✓ Professional UI with badges and summaries")
    print("✓ Edit/Delete capabilities for corrections")
    print("✓ API endpoints for quick clock in/out")
    print("=" * 90 + "\n")
