from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Staff, Attendance
from datetime import datetime, timedelta
from sqlalchemy import func

bp = Blueprint('attendance', __name__, url_prefix='/attendance')

# --- Attendance Dashboard ---

@bp.route('/')
@login_required
def index():
    """Attendance dashboard with date filtering"""
    # Get date filter from request
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')
    staff_id_filter = request.args.get('staff_id')
    
    # Set default date range (current month)
    if not date_from_str:
        today = datetime.now()
        date_from = today.replace(day=1)
    else:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
    
    if not date_to_str:
        date_to = datetime.now()
    else:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d')
    
    # Get attendance records
    query = Attendance.query.filter(
        Attendance.date >= date_from.date(),
        Attendance.date <= date_to.date()
    )
    
    if staff_id_filter:
        query = query.filter(Attendance.staff_id == staff_id_filter)
    
    attendance_records = query.order_by(Attendance.date.desc(), Attendance.staff_id).all()
    
    # Calculate summary
    total_hours = 0
    total_minutes = 0
    total_earned = 0
    
    for record in attendance_records:
        total_hours += record.hours_worked
        total_minutes += record.minutes_worked
        total_earned += record.earned_amount
    
    # Convert minutes to hours
    total_hours += total_minutes // 60
    total_minutes = total_minutes % 60
    
    # Get all staff for filter dropdown
    all_staff = Staff.query.filter_by(is_active=True).all()
    
    return render_template('salary/attendance_list.html',
                         attendance_records=attendance_records,
                         all_staff=all_staff,
                         date_from=date_from_str or date_from.strftime('%Y-%m-%d'),
                         date_to=date_to_str or date_to.strftime('%Y-%m-%d'),
                         staff_id_filter=staff_id_filter,
                         total_hours=total_hours,
                         total_minutes=total_minutes,
                         total_earned=total_earned)

# --- Clock In/Out ---

@bp.route('/clock-in/<int:staff_id>', methods=['POST'])
@login_required
def clock_in(staff_id):
    """Staff clock in"""
    staff = Staff.query.get_or_404(staff_id)
    today = datetime.now().date()
    
    # Check if already clocked in today
    existing = Attendance.query.filter_by(
        staff_id=staff_id,
        date=today
    ).first()
    
    if existing and existing.clock_in and not existing.clock_out:
        flash(f'{staff.name} is already clocked in!', 'warning')
        return redirect(url_for('attendance.index'))
    
    if not existing:
        # Create new attendance record
        attendance = Attendance(
            staff_id=staff_id,
            date=today,
            clock_in=datetime.now()
        )
        attendance.calculate_hourly_rate()
        db.session.add(attendance)
    else:
        # Update existing record (if they clocked out earlier)
        existing.clock_in = datetime.now()
    
    db.session.commit()
    flash(f'{staff.name} clocked in at {datetime.now().strftime("%H:%M:%S")}', 'success')
    return redirect(url_for('attendance.index'))

@bp.route('/clock-out/<int:staff_id>', methods=['POST'])
@login_required
def clock_out(staff_id):
    """Staff clock out"""
    staff = Staff.query.get_or_404(staff_id)
    today = datetime.now().date()
    
    # Find today's attendance record
    attendance = Attendance.query.filter_by(
        staff_id=staff_id,
        date=today
    ).first()
    
    if not attendance:
        flash(f'No clock in record found for {staff.name} today!', 'danger')
        return redirect(url_for('attendance.index'))
    
    if not attendance.clock_in:
        flash(f'{staff.name} has not clocked in yet!', 'warning')
        return redirect(url_for('attendance.index'))
    
    if attendance.clock_out:
        flash(f'{staff.name} has already clocked out!', 'info')
        return redirect(url_for('attendance.index'))
    
    # Set clock out time and calculate
    attendance.clock_out = datetime.now()
    attendance.calculate_hours_worked()
    attendance.calculate_earned_amount()
    
    db.session.commit()
    flash(f'{staff.name} clocked out at {attendance.clock_out.strftime("%H:%M:%S")}. Worked: {attendance.get_time_summary()}', 'success')
    return redirect(url_for('attendance.index'))

# --- Attendance Management ---

@bp.route('/record/<int:attendance_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_attendance(attendance_id):
    """Edit attendance record (for manual corrections)"""
    attendance = Attendance.query.get_or_404(attendance_id)
    
    if request.method == 'POST':
        # Parse clock in time
        clock_in_str = request.form.get('clock_in')
        clock_out_str = request.form.get('clock_out')
        notes = request.form.get('notes')
        
        try:
            if clock_in_str:
                date_str = request.form.get('date', str(attendance.date))
                attendance.clock_in = datetime.strptime(f"{date_str} {clock_in_str}", '%Y-%m-%d %H:%M')
            
            if clock_out_str:
                date_str = request.form.get('date', str(attendance.date))
                attendance.clock_out = datetime.strptime(f"{date_str} {clock_out_str}", '%Y-%m-%d %H:%M')
            
            attendance.notes = notes
            attendance.calculate_hours_worked()
            attendance.calculate_earned_amount()
            
            db.session.commit()
            flash('Attendance record updated!', 'success')
            return redirect(url_for('attendance.index'))
        except ValueError as e:
            flash(f'Invalid time format: {e}', 'danger')
    
    return render_template('salary/edit_attendance.html', attendance=attendance)

@bp.route('/record/<int:attendance_id>/delete', methods=['POST'])
@login_required
def delete_attendance(attendance_id):
    """Delete attendance record"""
    attendance = Attendance.query.get_or_404(attendance_id)
    staff_name = attendance.staff.name
    db.session.delete(attendance)
    db.session.commit()
    flash(f'Attendance record for {staff_name} deleted.', 'info')
    return redirect(url_for('attendance.index'))

# --- API Endpoints for AJAX ---

@bp.route('/api/quick-clock/<int:staff_id>/<action>', methods=['POST'])
@login_required
def quick_clock(staff_id, action):
    """Quick clock in/out via API"""
    try:
        if action == 'in':
            result = clock_in(staff_id)
        elif action == 'out':
            result = clock_out(staff_id)
        else:
            return jsonify({'status': 'error', 'message': 'Invalid action'}), 400
        
        return jsonify({'status': 'success', 'message': f'Action: {action}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@bp.route('/api/staff/<int:staff_id>/today-status')
@login_required
def staff_today_status(staff_id):
    """Get staff's today status"""
    today = datetime.now().date()
    attendance = Attendance.query.filter_by(
        staff_id=staff_id,
        date=today
    ).first()
    
    status = {
        'staff_id': staff_id,
        'date': str(today),
        'clocked_in': False,
        'clocked_out': False,
        'time_summary': '0h 0m',
        'earned': 0
    }
    
    if attendance:
        status['clocked_in'] = attendance.clock_in is not None
        status['clocked_out'] = attendance.clock_out is not None
        status['time_summary'] = attendance.get_time_summary()
        status['earned'] = round(attendance.earned_amount, 2)
    
    return jsonify(status)
