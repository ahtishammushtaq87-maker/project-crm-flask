# 🎯 ATTENDANCE SYSTEM - QUICK REFERENCE GUIDE

## 🚀 Quick Start

### Access Attendance Dashboard
```
URL: http://localhost:5000/attendance/
```

### Clock In (Start Shift)
1. Go to `/attendance/`
2. Find your name in "Quick Clock" section
3. Click **[Clock In]** button
4. System records current time automatically

### Clock Out (End Shift)
1. Go to `/attendance/`
2. Find your name in "Quick Clock" section
3. Click **[Clock Out]** button
4. System calculates hours and earnings automatically

### View Your Attendance
1. Go to `/attendance/`
2. Leave date range as default (current month)
3. Select your name from "Staff" dropdown
4. See all your attendance records
5. View total hours and earnings at top

---

## 💰 Salary Calculation

### Your Hourly Rate
```
Hourly Rate = Monthly Salary ÷ 30 days ÷ 8 hours/day
```

**Example**:
```
Monthly: Rs 30,000
Hourly:  Rs 30,000 ÷ 30 ÷ 8 = Rs 125/hour
```

### Your Daily Earnings
```
Earnings = Hours Worked × Hourly Rate
```

**Examples**:
- 8 hours = 8 × Rs 125 = Rs 1,000
- 4 hours (half day) = 4 × Rs 125 = Rs 500
- 10 hours (overtime) = 10 × Rs 125 = Rs 1,250
- 6.5 hours = 6.5 × Rs 125 = Rs 812.50

---

## ⚙️ How It Works

### Step 1: Clock In
```
✓ You click "Clock In"
✓ System records current date & time
✓ Status shows "Clocked In"
```

### Step 2: Work
```
✓ You work for X hours
```

### Step 3: Clock Out
```
✓ You click "Clock Out"
✓ System records current date & time
✓ System automatically calculates:
  - Hours worked
  - Minutes worked
  - Hourly rate
  - Amount earned
```

### Step 4: Dashboard Shows
```
✓ Your attendance record saved
✓ Hours and minutes displayed
✓ Earnings calculated and shown
✓ Integrated into payroll
```

---

## 🎨 Dashboard Sections

### FILTERS
```
Date Range:  [From Date] [To Date]  [Filter Button]
Staff:       [Select Staff Member ▼]
```

**Tips**:
- Leave dates empty to see entire month
- Select specific staff or leave blank for all staff
- Click "Filter" to update results

### SUMMARY CARDS
```
┌─────────────────────────────────┐
│ Total Hours Worked: 57h 0m      │
│ Total Earned: Rs 1,187.50       │
│ Total Records: 4                │
└─────────────────────────────────┘
```

### QUICK CLOCK BUTTONS
```
Ahmed Ali (Rs 41.67/hr)
Daily Rate: Rs 333.33
[Clock In]  [Clock Out]  Last: 17:00
```

### ATTENDANCE TABLE
Columns:
- **Date**: When you worked
- **Staff**: Your name
- **In-Out**: Clock in and out times (HH:MM format)
- **Hours**: Total time worked (Xh Ym)
- **Rate**: Your hourly wage (Rs/hour)
- **Earned**: How much you made (Rs)
- **Notes**: Any special notes
- **Actions**: Edit or Delete buttons

---

## ✏️ Edit Attendance

### When to Edit
- You forgot to clock out
- You clocked in/out wrong time
- Need to add notes (half day, late, etc.)

### How to Edit
1. Click **[✏️]** button next to record
2. Adjust clock in/out times
3. Add notes if needed
4. Click "Save"
5. Earnings recalculate automatically

### Example Notes
- "Half day - medical appointment"
- "Overtime - project deadline"
- "Late - traffic delay"
- "Left early - meeting"

---

## 🗑️ Delete Record

### When to Delete
- Duplicate entry
- Wrong entry
- Entry recorded by mistake

### How to Delete
1. Click **[🗑️]** button next to record
2. Confirm deletion
3. Record is removed
4. Totals update automatically

---

## 📊 Understanding Your Report

### Daily Breakdown
```
Date: April 9, 2026
In:  09:00 AM
Out: 05:00 PM
Hours: 8h 0m
Rate: Rs 41.67/hour
Earned: Rs 333.33
```

### Weekly Summary (Example)
```
Monday:    8h 0m   Rs 333.33
Tuesday:   8h 0m   Rs 333.33
Wednesday: 8h 0m   Rs 333.33
Thursday:  8h 0m   Rs 333.33
Friday:    4h 0m   Rs 166.67
─────────────────────────────
Total:     36h 0m  Rs 1,500.00
```

### Monthly Summary (Example)
```
Working Days: 20
Average Hours: 8h 0m per day
Total Hours: 160h 0m
Total Earned: Rs 6,666.67
```

---

## ❓ Frequently Asked Questions

### Q: What if I forget to clock out?

**A**: Go to Attendance → Find the record → Click Edit → Enter clock out time → Save

---

### Q: How are partial hours calculated?

**A**: Minutes are converted to decimal:
```
6 hours 30 minutes = 6.5 hours
30 minutes ÷ 60 = 0.5 hours
```

---

### Q: What time format should I use?

**A**: 24-hour format (HH:MM):
```
9:00 AM  = 09:00
5:00 PM  = 17:00
6:30 PM  = 18:30
```

---

### Q: Can I clock in multiple times per day?

**A**: No, one record per day. If needed:
1. Edit the existing record
2. Adjust the clock out time
3. Or delete and create new if needed

---

### Q: When does the payroll update?

**A**: Automatically when:
- You clock out (updates earnings)
- You edit an attendance record
- Dashboard recalculates on page load

---

### Q: How is my hourly rate calculated?

**A**: Automatically from your salary:
```
Hourly Rate = Monthly Salary ÷ 30 days ÷ 8 hours/day

Example: Rs 30,000 monthly
= Rs 30,000 ÷ 30 = Rs 1,000 daily
= Rs 1,000 ÷ 8 = Rs 125 hourly
```

---

### Q: Do I get paid for overtime?

**A**: Yes! Overtime hours are calculated at the same hourly rate:
```
If you work 10 hours instead of 8
Earnings = 10 hours × Hourly Rate
= 10 × Rs 125 = Rs 1,250 (instead of Rs 1,000)
```

---

### Q: Can I view other staff's attendance?

**A**: Only if you have permission (admin/manager role).

---

### Q: What happens if I don't clock out?

**A**: Your hours won't be recorded. You must:
1. Clock out manually
2. Or go back and edit to add clock out time

---

## 🔔 Important Notes

⚠️ **Always Clock Out**
- Forgetting to clock out means hours aren't recorded
- Earnings won't be calculated without clock out time
- Edit as soon as possible if you forget

⚠️ **Accurate Times**
- Enter times accurately for correct wage calculation
- Edit if you notice mistakes
- Add notes explaining any unusual entries

⚠️ **Date Format**
- Use YYYY-MM-DD for dates (2026-04-09)
- Use HH:MM for times (09:00, 17:30)

⚠️ **Payroll Integration**
- Attendance earnings feed into main payroll
- Dashboard calculates total from all staff attendance
- Payments based on actual hours worked

---

## 💡 Tips & Tricks

### Tip 1: Set Phone Reminder
Set a daily reminder to clock out at end of shift to avoid forgetting.

### Tip 2: Keep Notes
Add notes for special circumstances (sick leave, half day, overtime) for record keeping.

### Tip 3: Check Weekly
Regularly check your attendance records to ensure accuracy.

### Tip 4: Edit Immediately
If you notice a mistake, edit it immediately before payroll runs.

### Tip 5: Screenshot Summary
Take screenshot of weekly/monthly summary for your records.

---

## 📞 Need Help?

### Attendance Not Showing?
1. Make sure you clicked "Clock Out"
2. Refresh the page
3. Check date range filter

### Earnings Wrong?
1. Check clock in/out times
2. Verify hourly rate calculation
3. Edit record if needed

### Can't Edit Record?
1. Check if you have permission
2. Contact your manager/admin

### Other Issues?
Contact: [Admin/Manager Contact]

---

## 🎯 Best Practices

✅ **DO**
- Clock in at start of shift
- Clock out at end of shift
- Edit mistakes immediately
- Add notes for special situations
- Check records regularly

❌ **DON'T**
- Forget to clock out
- Enter wrong times
- Leave typos in times
- Delay fixing mistakes
- Clock in multiple times per day

---

## 📅 Calendar View

### April 2026 Example
```
      S   M   T   W   T   F   S
         1   2   3   4   5   6
   7   8   9  10  11  12  13
  14  15  16  17  18  19  20
  21  22  23  24  25  26  27
  28  29  30

Worked: 20 days
Total Hours: 160h
Total Earnings: Rs 6,666.67
Average/Day: Rs 333.33
```

---

**Quick Links**:
- Main Dashboard: `/attendance/`
- Edit Record: `/attendance/record/<id>/edit`
- Help: Contact Admin

---

**Last Updated**: 2026-04-09
**Version**: 1.0 - Quick Reference
