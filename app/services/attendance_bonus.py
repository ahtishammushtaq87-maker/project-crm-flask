"""Perfect-attendance bonus: one day's pay for a month worked exactly to plan.

A staff member qualifies for a month when BOTH hold:
  * hours earned == hours required for that month (no shortfall, no surplus)
  * no overtime was logged anywhere in that month

Required hours come from app.utils.get_required_hours_in_range - 8h for every
non-Sunday day, minus that staff's holiday-marked days - so the rule is the
same one the Attendance list already shows as "Required Hours".

The award is written as an approved SalaryAdjustment of type 'bonus' targeting
that payroll month, which is exactly what pay_salary() already picks up and
pre-fills into the month's Bonus field (see app/routes/salary.py) - so no
payroll code needed changing for this to reach the payslip.

is_auto_attendance_bonus doubles as the idempotency key: one auto row per
staff per payroll month in ANY status. Rejecting a row therefore suppresses it
for good rather than having the job re-create it on the next run.
"""
from calendar import monthrange
from datetime import date, datetime

from app import db
from app.models import Attendance, SalaryAdjustment, Staff
from app.utils import get_required_hours_in_range, get_working_days_in_month

# Hours may be entered as 8 and 0 minutes, or 7h60m, or land on a rounding
# artifact - treat anything inside this window as an exact match.
HOURS_TOLERANCE = 0.01


def _month_bounds(month, year):
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _logged_overtime_hours(staff, month_start, month_end):
    """Overtime explicitly recorded on attendance rows for the month."""
    total = 0.0
    for record in staff.attendance_records:
        if month_start <= record.date <= month_end:
            total += (record.overtime_hours or 0) + (record.overtime_minutes or 0) / 60.0
    return total


def _one_day_pay(staff, month, year):
    """A single day's pay for this specific month - monthly salary divided by
    that month's actual working days (non-Sundays minus this staff's
    holidays), matching Staff.calculate_daily_salary(). Computed here rather
    than calling that method, because it writes to staff.daily_salary and this
    job must not mutate staff rows.
    """
    working_days = get_working_days_in_month(year, month)
    month_start, month_end = _month_bounds(month, year)
    holidays = sum(
        1 for a in staff.attendance_records
        if a.is_holiday and month_start <= a.date <= month_end
    )
    actual_working_days = max(1, working_days - holidays)
    return (staff.monthly_salary or 0) / float(actual_working_days)


def evaluate_staff_month(staff, month, year):
    """The eligibility picture for one staff member and one month."""
    month_start, month_end = _month_bounds(month, year)

    required = get_required_hours_in_range(staff, month_start, month_end)
    earned = staff.get_total_hours(month_start, month_end)
    overtime = _logged_overtime_hours(staff, month_start, month_end)

    eligible = (
        required > 0
        and abs(earned - required) <= HOURS_TOLERANCE
        and overtime <= HOURS_TOLERANCE
    )

    return {
        'staff': staff,
        'required_hours': required,
        'earned_hours': earned,
        'overtime_hours': overtime,
        'eligible': eligible,
        'bonus_amount': _one_day_pay(staff, month, year) if eligible else 0.0,
    }


def already_awarded(staff_id, month, year):
    return SalaryAdjustment.query.filter_by(
        staff_id=staff_id,
        payroll_month=month,
        payroll_year=year,
        is_auto_attendance_bonus=True,
    ).first()


def award_perfect_attendance_bonuses(month=None, year=None):
    """Create the approved bonus rows for every staff member who qualified in
    the given month (defaults to the current one). Safe to call repeatedly -
    a staff member who already has an auto row for the month is skipped.
    Returns the number of rows created.
    """
    today = date.today()
    month = month or today.month
    year = year or today.year

    month_label = date(year, month, 1).strftime('%B %Y')
    created = 0

    for staff in Staff.query.filter_by(is_active=True).all():
        if already_awarded(staff.id, month, year):
            continue

        result = evaluate_staff_month(staff, month, year)
        if not result['eligible'] or result['bonus_amount'] <= 0:
            continue

        db.session.add(SalaryAdjustment(
            staff_id=staff.id,
            adjustment_type='bonus',
            amount=round(result['bonus_amount'], 2),
            reason=f'Perfect attendance bonus (1 day) - {month_label}',
            is_recurring=False,
            payroll_month=month,
            payroll_year=year,
            evidence_text=(
                f"Auto-awarded: {result['earned_hours']:.2f}h worked against "
                f"{result['required_hours']:.2f}h required, no overtime logged."
            ),
            status='approved',
            approved_at=datetime.utcnow(),
            is_applied=False,
            is_auto_attendance_bonus=True,
        ))
        created += 1

    if created:
        db.session.commit()

    return created


def run_for_recent_months():
    """What the scheduler and the Adjustments page call: evaluate the current
    month and the one before it. The previous month is included so a month
    that completed while nobody was looking still gets awarded, and the
    current month is included so the bonus appears as soon as its final
    attendance is entered.
    """
    today = date.today()
    prev_month = 12 if today.month == 1 else today.month - 1
    prev_year = today.year - 1 if today.month == 1 else today.year

    return (award_perfect_attendance_bonuses(prev_month, prev_year)
            + award_perfect_attendance_bonuses(today.month, today.year))
