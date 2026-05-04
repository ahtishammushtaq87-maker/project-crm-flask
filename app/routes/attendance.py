from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from app.utils import permission_required
from flask_login import login_required, current_user
from app import db
from app.models import Staff, Attendance
from datetime import datetime, timedelta
from sqlalchemy import func
from app.routes.filters import apply_saved_filter_to_query

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
        
    query = apply_saved_filter_to_query(query, 'attendance', request.args)
    
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
                         total_hours=total_hours,
                         total_minutes=total_minutes,
                         total_earned=total_earned,
                         active_module='attendance')

# --- Clock In/Out ---

@bp.route('/clock-in/<int:staff_id>', methods=['POST'])
@login_required
@permission_required('attendance', action='add')
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
@permission_required('attendance', action='edit')
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
@permission_required('attendance', action='edit')
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
@permission_required('attendance', action='delete')
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
@permission_required('attendance', action='edit')
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

def parse_time(time_val, att_date):
    """Robustly parse time value from Excel into a datetime object."""
    from datetime import datetime, time as datetime_time
    if not time_val:
        return None
        
    if isinstance(time_val, datetime):
        # Already a datetime, just ensure it's on the correct date
        return datetime.combine(att_date, time_val.time())
    
    if isinstance(time_val, datetime_time):
        # It's a time object, combine with the attendance date
        return datetime.combine(att_date, time_val)
        
    # Handle string formats
    time_str = str(time_val).strip()
    formats = ['%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M:%S %p']
    
    for fmt in formats:
        try:
            parsed_t = datetime.strptime(time_str, fmt).time()
            return datetime.combine(att_date, parsed_t)
        except ValueError:
            continue
            
    raise ValueError(f"Invalid time format: {time_str}")

@bp.route('/bulk-upload', methods=['GET', 'POST'])
@login_required
@permission_required('attendance', action='add')
def bulk_upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(url_for('attendance.bulk_upload'))
            
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('attendance.bulk_upload'))
            
        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('Please upload an Excel file (.xlsx or .xls)', 'error')
            return redirect(url_for('attendance.bulk_upload'))
            
        try:
            from openpyxl import load_workbook
            from io import BytesIO
            from datetime import datetime
            file_content = file.read()
            wb = load_workbook(filename=BytesIO(file_content), data_only=True, read_only=True)
            ws = wb.active
            rows = list(ws.values)
            if not rows or len(rows) < 2:
                flash('File is empty or contains no data rows', 'error')
                return redirect(url_for('attendance.bulk_upload'))
                
            headers = [str(h).strip().lower() if h else '' for h in rows[0]]
            
            required_columns = ['staff_name', 'date', 'clock_in_time']
            missing = [col for col in required_columns if col not in headers]
            if missing:
                flash(f'Missing required columns: {", ".join(missing)}', 'error')
                return redirect(url_for('attendance.bulk_upload'))
                
            added = 0
            errors = []
            
            for idx, row in enumerate(rows[1:], start=2):
                # Skip truly empty rows
                if not any(row):
                    continue
                    
                try:
                    row_dict = {}
                    for i, val in enumerate(row):
                        if i < len(headers):
                            row_dict[headers[i]] = val
                            
                    staff_name = str(row_dict.get('staff_name', '')).strip()
                    if not staff_name:
                        errors.append(f'Row {idx}: Missing staff_name')
                        continue
                        
                    staff = Staff.query.filter_by(name=staff_name).first()
                    if not staff:
                        errors.append(f'Row {idx}: Staff "{staff_name}" not found')
                        continue

                        
                    date_val = row_dict.get('date')
                    if isinstance(date_val, datetime):
                        att_date = date_val.date()
                    elif date_val:
                        try:
                            # Split in case of "2024-05-01 00:00:00" strings
                            date_str = str(date_val).split()[0]
                            att_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        except ValueError:
                            errors.append(f'Row {idx}: Invalid date format (expected YYYY-MM-DD)')
                            continue
                    else:
                        errors.append(f'Row {idx}: Missing date')
                        continue
                        
                    # Check for duplicate entry in same file/db
                    existing = Attendance.query.filter_by(staff_id=staff.id, date=att_date).first()
                    if existing:
                        errors.append(f'Row {idx}: Attendance for staff {staff.name} on {att_date} already exists')
                        continue
                        
                    try:
                        clock_in = parse_time(row_dict.get('clock_in_time'), att_date)
                        if not clock_in:
                            errors.append(f'Row {idx}: Missing clock_in_time')
                            continue
                            
                        clock_out = parse_time(row_dict.get('clock_out_time'), att_date)
                    except ValueError as ve:
                        errors.append(f'Row {idx}: {str(ve)}')
                        continue
                        
                    attendance = Attendance(
                        staff_id=staff.id,
                        date=att_date,
                        clock_in=clock_in,
                        clock_out=clock_out,
                        notes=str(row_dict.get('notes', '')).strip() if row_dict.get('notes') else None
                    )
                    
                    if clock_out:
                        attendance.calculate_hours_worked()
                        attendance.calculate_earned_amount()
                    else:
                        attendance.calculate_hourly_rate()
                        
                    db.session.add(attendance)
                    added += 1
                except Exception as e:
                    errors.append(f'Row {idx}: {str(e)}')
            
            if added > 0:
                db.session.commit()
                flash(f'Successfully added {added} attendance records!', 'success')
            
            if errors:
                flash(f'Encountered {len(errors)} issues. First 5 shown: {"; ".join(errors[:5])}', 'warning')
                
            if added == 0 and not errors:
                flash('No data entries found in file.', 'info')
                
            return redirect(url_for('attendance.index'))
        except Exception as e:
            flash(f'Error reading file: {str(e)}', 'error')
            return redirect(url_for('attendance.bulk_upload'))
            
    return render_template('salary/attendance_bulk_upload.html')


@bp.route('/download-sample')
@login_required
def download_sample():
    try:
        from openpyxl import Workbook
        from io import BytesIO
        from flask import send_file
        from datetime import datetime, date
        
        wb = Workbook()
        ws = wb.active
        ws.title = 'Attendance'
        
        headers = ['staff_name', 'date', 'clock_in_time', 'clock_out_time', 'notes']
        ws.append(headers)
        
        staff = Staff.query.first()
        staff_name = staff.name if staff else "John Doe"
        
        today = datetime.now().date()
        current_date_str = today.strftime('%Y-%m-%d')
        
        sample_data = [
            [staff_name, current_date_str, '09:00:00', '17:00:00', 'Regular day'],
            [staff_name, current_date_str, '09:15:00', '18:30:00', 'Overtime']
        ]
        
        for row in sample_data:
            ws.append(row)

            
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, download_name='sample_attendance.xlsx', as_attachment=True)

    except Exception as e:
        flash(f'Error creating sample: {str(e)}', 'error')
        return redirect(url_for('attendance.bulk_upload'))
