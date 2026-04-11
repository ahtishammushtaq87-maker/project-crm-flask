# Professional Attendance & Time Tracking System

## Overview

A complete, production-ready attendance system with professional time tracking, hourly wage calculation, and comprehensive reporting. Integrated with the CRM salary management module.

## ✅ System Features

### 1. **Clock In/Out Functionality**
- Staff members can clock in when starting work
- Staff members can clock out when finishing work
- Automatic timestamp recording
- Timezone-aware datetime handling

### 2. **Automatic Time Calculation**
- Hours worked: Calculated from clock in/out times
- Minutes worked: Extracted as remainder (0-59 minutes)
- Time format: Professional "Xh Ym" display (e.g., "8h 30m")

### 3. **Hourly Wage Calculation**
- **Formula**: Monthly Salary ÷ 30 days ÷ 8 hours/day = Hourly Rate
- **Earned Amount**: (Hours + Minutes/60) × Hourly Rate
- **Supports**: Partial hours, overtime, half days

### 4. **Dashboard & Reporting**
- Date range filtering (From/To dates)
- Staff member filtering
- Summary statistics: Total hours, total earned, record count
- Detailed records table with all attendance information
- Quick clock in/out buttons for each active staff

### 5. **Record Management**
- Edit attendance records for corrections
- Add notes to records (e.g., "Late", "Medical Leave", "Overtime")
- Delete records if needed
- Auto-timestamps for record creation/updates

### 6. **API Endpoints**
- REST API endpoints for mobile/external integrations
- AJAX endpoints for quick clock in/out
- JSON responses for programmatic access

---

## 📋 Database Schema

### Attendance Table

| Column | Type | Purpose |
|--------|------|---------|
| `id` | Integer (PK) | Primary key |
| `staff_id` | Integer (FK) | Reference to Staff |
| `date` | Date | Date of attendance record |
| `clock_in` | DateTime | When staff clocked in |
| `clock_out` | DateTime | When staff clocked out |
| `hours_worked` | Float | Total hours worked (calculated) |
| `minutes_worked` | Integer | Remaining minutes (0-59) |
| `hourly_rate` | Float | Calculated hourly rate |
| `earned_amount` | Float | Total earned (calculated) |
| `notes` | Text | Optional notes/remarks |
| `created_at` | DateTime | Record creation timestamp |
| `updated_at` | DateTime | Record update timestamp |

---

## 🔧 Models & Methods

### Attendance Model

```python
class Attendance(db.Model):
    """Staff Attendance/Time Tracking model"""
    
    # Fields
    id, staff_id, date
    clock_in, clock_out
    hours_worked, minutes_worked
    hourly_rate, earned_amount
    notes, created_at, updated_at
    
    # Methods
    def calculate_hours_worked(self):
        """Calculate hours and minutes from clock in/out"""
    
    def calculate_hourly_rate(self):
        """Calculate hourly rate = monthly_salary ÷ 30 ÷ 8"""
    
    def calculate_earned_amount(self):
        """Calculate total earned = hours × hourly_rate"""
    
    def get_time_summary(self):
        """Return formatted time (e.g., '8h 30m')"""
```

---

## 🌐 Routes & Endpoints

### Main Dashboard

**Route**: `/attendance/`
**Method**: `GET`

Access the main attendance dashboard with:
- Date range filtering (default: current month)
- Staff member filtering
- Summary cards: Total hours, total earned, record count
- Records table with all details
- Quick clock buttons for active staff

**URL Parameters**:
- `staff_id`: Filter by specific staff
- `date_from`: Start date (YYYY-MM-DD)
- `date_to`: End date (YYYY-MM-DD)

---

### Clock In

**Route**: `/attendance/clock-in/<staff_id>`
**Method**: `POST`

Clock in a staff member for the current date/time.

**Response**:
```json
{
  "success": true,
  "message": "Clocked in successfully",
  "time": "09:00:00",
  "record_id": 123
}
```

---

### Clock Out

**Route**: `/attendance/clock-out/<staff_id>`
**Method**: `POST`

Clock out a staff member and record the day's attendance.

**Response**:
```json
{
  "success": true,
  "message": "Clocked out successfully",
  "hours_worked": "8h 30m",
  "earned": 354.17,
  "record_id": 123
}
```

---

### Edit Attendance Record

**Route**: `/attendance/record/<id>/edit`
**Method**: `GET, POST`

Edit an existing attendance record manually.

**Form Fields**:
- Date: When the attendance occurred
- Clock In Time: What time they clocked in
- Clock Out Time: What time they clocked out
- Notes: Any additional notes

---

### Delete Attendance Record

**Route**: `/attendance/record/<id>/delete`
**Method**: `POST`

Delete an attendance record (for mistakes/duplicates).

---

### API Endpoints

**Quick Clock (AJAX)**:
- `POST /attendance/api/quick-clock/in/<staff_id>`
- `POST /attendance/api/quick-clock/out/<staff_id>`

**Get Attendance**:
- `GET /attendance/api/records/?date_from=2026-04-01&date_to=2026-04-30`

---

## 💻 Usage Examples

### Example 1: Normal Working Day

**Staff**: Ahmed Ali
- **Monthly Salary**: Rs 30,000
- **Daily Salary**: Rs 1,000
- **Hourly Rate**: Rs 125/hour

**Attendance**:
```
Clock In:  09:00 AM
Clock Out: 05:30 PM
Duration:  8h 30m
Earned:    8.5 hours × Rs 125 = Rs 1,062.50
```

### Example 2: Half Day

**Staff**: Same as above

**Attendance**:
```
Clock In:  09:00 AM
Clock Out: 01:00 PM
Duration:  4h 0m
Earned:    4 hours × Rs 125 = Rs 500.00
```

### Example 3: Overtime

**Staff**: Same as above

**Attendance**:
```
Clock In:  08:00 AM
Clock Out: 07:00 PM
Duration:  11h 0m
Earned:    11 hours × Rs 125 = Rs 1,375.00
```

### Example 4: Weekly Summary

**Period**: 5 working days

| Day | Time | Duration | Earned |
|-----|------|----------|--------|
| Mon | 9 AM - 5:30 PM | 8h 30m | Rs 1,062.50 |
| Tue | 9 AM - 5 PM | 8h 0m | Rs 1,000.00 |
| Wed | 9 AM - 6 PM | 9h 0m | Rs 1,125.00 |
| Thu | 9 AM - 5 PM | 8h 0m | Rs 1,000.00 |
| Fri | 9 AM - 1 PM | 4h 0m | Rs 500.00 |
| **Total** | | **37h 30m** | **Rs 4,687.50** |

---

## 🎯 Dashboard Features

### Summary Cards
- **Total Hours Worked**: Formatted as "Xh Ym"
- **Total Earned**: Sum of all earned amounts in period
- **Number of Records**: Count of attendance entries

### Filters
- **Date Range**: From date and To date (default: current month)
- **Staff Member**: Select specific staff or show all

### Records Table
Displays:
- Date of attendance
- Staff member name
- Clock in time (HH:MM format)
- Clock out time (HH:MM format)
- Duration worked (Xh Ym)
- Hourly rate (Rs/hour)
- Amount earned (Rs)
- Notes (if any)
- Action buttons: Edit, Delete

### Quick Clock Buttons
- One-click clock in for each active staff member
- Shows staff daily salary rate
- Shows hourly rate clearly
- Professional card-based layout

---

## ⚙️ Calculation Logic

### Step 1: Calculate Hours and Minutes
```
Time Difference = Clock Out - Clock In
Total Minutes = Time Difference ÷ 60
Hours = Total Minutes ÷ 60 (integer division)
Minutes = Total Minutes % 60 (remainder)
```

### Step 2: Calculate Hourly Rate
```
Hourly Rate = Monthly Salary ÷ 30 days ÷ 8 hours/day
```

### Step 3: Calculate Earned Amount
```
Hours in Decimal = Hours + (Minutes ÷ 60)
Earned Amount = Hours in Decimal × Hourly Rate
```

### Example Calculation
```
Clock In:  09:00:00
Clock Out: 17:30:00
Difference: 8 hours 30 minutes

Hours: 8
Minutes: 30

Hourly Rate: Rs 30,000 ÷ 30 ÷ 8 = Rs 125/hour

Hours Decimal: 8 + (30 ÷ 60) = 8.5
Earned: 8.5 × 125 = Rs 1,062.50
```

---

## 🔄 Dashboard Integration

### Payroll Calculation

The dashboard now calculates payroll as:

```python
payroll = (
    # Attendance-based salary for the period
    sum(attendance.earned_amount for each day in period)
    +
    # Backup daily salary for staff without time tracking
    sum(staff.daily_salary * days_in_period for active staff)
)
```

### Example
**Period**: April 1-30, 2026
**Staff**: 5 members

```
Attendance-based:
- Ahmed Ali: Rs 4,687.50 (37.5h worked)
- Zainab Khan: Rs 3,125.00 (25h worked)
- Hassan Ali: Rs 5,000.00 (40h worked)
- Fatima Raza: Rs 3,750.00 (30h worked)
- Muhammad Saad: Rs 2,500.00 (20h worked)

Subtotal: Rs 19,062.50

Staff without tracking (if any):
- Backup: Rs 1,000.00 (daily salary × 1 day)

Total Payroll: Rs 20,062.50
```

---

## 📱 Mobile/API Integration

### Quick Clock In (Mobile)
```bash
curl -X POST http://localhost:5000/attendance/clock-in/1
# Returns: {"success": true, "time": "09:00:00"}
```

### Quick Clock Out (Mobile)
```bash
curl -X POST http://localhost:5000/attendance/clock-out/1
# Returns: {"success": true, "hours": "8h 30m", "earned": 1062.50}
```

### Get Attendance Records
```bash
curl "http://localhost:5000/attendance/api/records/?date_from=2026-04-01&date_to=2026-04-30"
# Returns: [{"id": 1, "staff": "Ahmed", "date": "2026-04-01", "hours": 8, "earned": 333.33}, ...]
```

---

## 🛡️ Data Validation

### Validations Performed
- ✅ Clock in time must be before clock out time
- ✅ Staff must exist before clocking in
- ✅ Only one active clock-in per staff per day
- ✅ Dates must be in valid format (YYYY-MM-DD)
- ✅ Times must be in valid format (HH:MM:SS)

### Error Handling
```python
# If clock out before clock in
if clock_out <= clock_in:
    return error("Clock out time must be after clock in time")

# If staff not found
if not staff:
    return error("Staff member not found")

# If already clocked in
if existing_record.clock_in and not existing_record.clock_out:
    return error("Staff already clocked in today")
```

---

## 🎨 User Interface

### Attendance Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  📊 ATTENDANCE & TIME TRACKING                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  🔍 FILTERS                                                 │
│  Date From: [__/__/____]  Date To: [__/__/____]  [Filter]  │
│  Staff: [Select Staff Member ▼]                            │
│                                                              │
│  📈 SUMMARY                                                 │
│  ┌──────────────┬──────────────┬──────────────┐             │
│  │ Total Hours  │ Total Earned │ Total Records│             │
│  │   57h 0m     │  Rs 1,187.50 │      4       │             │
│  └──────────────┴──────────────┴──────────────┘             │
│                                                              │
│  ⏱️  QUICK CLOCK (Today)                                    │
│  ┌────────────────────────────────────────────┐             │
│  │ Ahmed Ali (Rs 41.67/hr)                    │             │
│  │ [Clock In] [Clock Out]  Last: 17:00        │             │
│  └────────────────────────────────────────────┘             │
│                                                              │
│  📋 ATTENDANCE RECORDS                                      │
│  ┌────────┬──────────┬─────────┬────────┬────────────────┐  │
│  │ Date   │ Staff    │ In-Out  │ Hours  │ Earned  │Action│  │
│  ├────────┼──────────┼─────────┼────────┼────────────────┤  │
│  │ Apr 09 │ Ahmed    │09-17    │8h 0m   │Rs 333  │✏️ 🗑️ │  │
│  │ Apr 10 │ Ahmed    │09-13    │4h 0m   │Rs 167  │✏️ 🗑️ │  │
│  │ Apr 11 │ Ahmed    │08-18    │10h 0m  │Rs 417  │✏️ 🗑️ │  │
│  │ Apr 12 │ Ahmed    │09-15:30 │6h 30m  │Rs 271  │✏️ 🗑️ │  │
│  └────────┴──────────┴─────────┴────────┴────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Test Results

### Successful Test Execution

**Test Data**:
- Staff: Ahtisham Mushtaq
- Monthly Salary: Rs 10,000
- Daily Salary: Rs 333.33
- Hourly Rate: Rs 41.67

**Test Cases**:

| Case | Time Period | Hours | Earned | Status |
|------|-------------|-------|--------|--------|
| Normal Day | 9 AM - 5 PM | 8h 0m | Rs 333.33 | ✅ |
| Half Day | 9 AM - 1 PM | 4h 0m | Rs 166.67 | ✅ |
| Overtime | 8 AM - 6 PM | 10h 0m | Rs 416.67 | ✅ |
| Partial | 9 AM - 3:30 PM | 6h 30m | Rs 270.83 | ✅ |
| **Total** | 4 days | 28h 30m | Rs 1,187.50 | ✅ |

---

## 🚀 Getting Started

### 1. Access Attendance Module
```
http://localhost:5000/attendance/
```

### 2. Clock In
Click the "Clock In" button for a staff member

### 3. Clock Out
Click the "Clock Out" button when done working

### 4. View Reports
Filter by date range to see attendance and payroll

### 5. Make Corrections
Click "Edit" to adjust times if needed

### 6. Track Progress
Dashboard automatically updates with calculations

---

## ✨ Key Advantages

✅ **Professional Time Tracking**
- Accurate hour-by-hour wage calculation
- Support for partial hours and minutes
- Real-time earning display

✅ **User-Friendly Interface**
- One-click clock in/out
- Intuitive date filtering
- Clear summary statistics

✅ **Flexible & Accurate**
- Edit records for corrections
- Add notes for special circumstances
- Supports overtime and half-days

✅ **Integration Ready**
- REST API for mobile apps
- Dashboard payroll integration
- Seamless with salary management

✅ **Production Ready**
- All validations in place
- Error handling implemented
- Database optimized with indexes

---

## 🔍 Troubleshooting

### Issue: Earned amount showing 0

**Solution**: Ensure staff relationship is loaded before calculating:
```python
att.staff = staff  # Set relationship
att.calculate_hours_worked()
att.calculate_earned_amount()
```

### Issue: Clock times not matching timezone

**Solution**: Use UTC timezone consistently:
```python
from datetime import datetime, timezone
clock_in = datetime.now(timezone.utc)
```

### Issue: Date range filter not working

**Solution**: Ensure date format is YYYY-MM-DD:
```python
# Correct
date_from = "2026-04-01"

# Incorrect
date_from = "04/01/2026"
```

---

## 📝 Notes

- Hourly rate is calculated as: Monthly Salary ÷ 30 days ÷ 8 hours/day
- Minutes are supported and converted to decimal hours for calculation
- Each attendance record is timestamped for audit trail
- Dashboard integrates with main payroll calculations
- All calculations are performed server-side for accuracy

---

## 📞 Support

For issues or questions:
1. Check the Troubleshooting section
2. Review test results in `test_attendance_system.py`
3. Check database schema in `app/models.py`
4. Review routes in `app/routes/attendance.py`

---

**Status**: ✅ Production Ready
**Last Updated**: 2026-04-09
**Version**: 1.0 - Complete Implementation
