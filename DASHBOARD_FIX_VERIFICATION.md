# ✅ ISSUE FIXED: Dashboard Expense Calculation

## Problem Statement
Dashboard was showing **full Rs 77,000** as operating expense instead of recognizing it as a **divided monthly expense** and showing only the **proportional amount (Rs 23,100)** for April 1-9.

**Wrong Display (Before):**
```
Total Expenses: Rs 77,000.00
Op: Rs 77,000.00 | BOM: Rs 0.00 | Pay: Rs 0.00
```

## Root Cause
The expense was properly marked as `is_monthly_divided=True` in the database, but the code wasn't filtering it out from the operating expenses calculation.

## Solution Applied

### Fixed Dashboard Route Logic
**File:** `app/routes/accounting.py` (Lines 92-186)

Changed from:
```python
# WRONG: Would include divided expenses in operating total
operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
    Expense.date >= date_from,
    Expense.date <= date_to
).scalar() or 0
```

To:
```python
# CORRECT: Explicitly excludes divided expenses
operating_expenses = db.session.query(func.sum(Expense.amount)).filter(
    Expense.is_bom_overhead == False,
    Expense.is_monthly_divided == False,  # ← IMPORTANT FILTER
    Expense.date >= date_from,
    Expense.date <= date_to
).scalar() or 0
```

### Added Separated Divided Expense Calculation (Lines 147-173)
```python
# For each divided expense, calculate PROPORTIONAL amount
for exp in monthly_divided_expenses:
    if exp.monthly_start_date and exp.monthly_end_date:
        overlap_start = max(exp.monthly_start_date, date_from.date())
        overlap_end = min(exp.monthly_end_date, date_to.date())
        
        if overlap_start <= overlap_end:
            overlap_days = (overlap_end - overlap_start).days + 1
            divided_expenses_for_period += exp.daily_amount * overlap_days
```

## Result - Correct Display (After)

✅ **Correct Display Now:**
```
Total Expenses: Rs 23,100.00
Op: Rs 0.00 | BOM: Rs 0.00 | Divided (Period): Rs 23,100.00 (2026-03-10 to 2026-04-09)
```

### Breakdown
| Component | Amount | Notes |
|-----------|--------|-------|
| Operating Expenses (Non-Divided) | Rs 0.00 | Correctly excluded divided expense |
| BOM Overhead (Non-Divided) | Rs 0.00 | No BOM expenses exist |
| **Divided Expenses (Proportional)** | **Rs 23,100.00** | 9 days × Rs 2,566.67/day |
| **TOTAL EXPENSES** | **Rs 23,100.00** | ✅ Correct (not full Rs 77,000) |

### Example Calculation
```
Full Expense: Rs 77,000 for April 1-30, 2026 (30 days)
Daily Rate: Rs 77,000 ÷ 30 = Rs 2,566.67/day

Dashboard Period: March 10 - April 9, 2026
Overlap: April 1-9 (9 days)
Proportional Amount: Rs 2,566.67 × 9 = Rs 23,100.00
```

## Verification
✅ All tests pass:
- Database columns verified
- Filters working correctly
- Proportional calculations accurate
- Dashboard displays correct values
- Net profit calculation uses proportional amounts

## To See Updated Dashboard
1. Open dashboard in browser
2. Default view shows last 30 days
3. Operating expenses: Rs 0 (divided expense excluded)
4. Divided expenses: Rs 23,100 (proportional for period)
5. Total: Rs 23,100 ✅

## Files Modified
- `app/routes/accounting.py` - Fixed dashboard route (Lines 92-186)
- `app/templates/accounting/dashboard.html` - Already shows correct breakdown

## Status: ✅ RESOLVED
The dashboard now correctly:
- ✅ Excludes divided expenses from operating totals
- ✅ Shows proportional divided amounts
- ✅ Uses correct values in profit calculations
- ✅ Displays clear expense breakdown
