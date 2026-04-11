from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Staff, SalaryAdvance, SalaryPayment
from app.forms import StaffForm, SalaryAdvanceForm, SalaryPaymentForm
from datetime import datetime
from sqlalchemy import extract

bp = Blueprint('salary', __name__)

# --- Staff Management ---

@bp.route('/staff')
@login_required
def staff_list():
    staff_members = Staff.query.all()
    return render_template('salary/staff_list.html', staff_members=staff_members)

@bp.route('/staff/add', methods=['GET', 'POST'])
@login_required
def add_staff():
    form = StaffForm()
    if form.validate_on_submit():
        staff = Staff(
            name=form.name.data,
            designation=form.designation.data,
            monthly_salary=form.monthly_salary.data,
            joining_date=form.joining_date.data or datetime.utcnow().date(),
            is_active=form.is_active.data
        )
        staff.calculate_daily_salary()  # Calculate daily salary
        db.session.add(staff)
        db.session.commit()
        flash('Staff member added successfully!', 'success')
        return redirect(url_for('salary.staff_list'))
    return render_template('salary/staff_form.html', form=form, title="Add Staff")

@bp.route('/staff/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_staff(id):
    staff = Staff.query.get_or_404(id)
    form = StaffForm(obj=staff)
    if form.validate_on_submit():
        staff.name = form.name.data
        staff.designation = form.designation.data
        staff.monthly_salary = form.monthly_salary.data
        staff.joining_date = form.joining_date.data
        staff.is_active = form.is_active.data
        staff.calculate_daily_salary()  # Recalculate daily salary
        db.session.commit()
        flash('Staff details updated!', 'success')
        return redirect(url_for('salary.staff_list'))
    return render_template('salary/staff_form.html', form=form, title="Edit Staff")

@bp.route('/staff/delete/<int:id>', methods=['POST'])
@login_required
def delete_staff(id):
    staff = Staff.query.get_or_404(id)
    db.session.delete(staff)
    db.session.commit()
    flash('Staff member deleted.', 'info')
    return redirect(url_for('salary.staff_list'))

# --- Salary Advances ---

@bp.route('/advances')
@login_required
def advance_list():
    advances = SalaryAdvance.query.order_by(SalaryAdvance.date.desc()).all()
    return render_template('salary/advance_list.html', advances=advances)

@bp.route('/advances/add', methods=['GET', 'POST'])
@login_required
def add_advance():
    form = SalaryAdvanceForm()
    form.staff_id.choices = [(s.id, s.name) for s in Staff.query.filter_by(is_active=True).all()]
    if form.validate_on_submit():
        advance = SalaryAdvance(
            staff_id=form.staff_id.data,
            amount=form.amount.data,
            date=form.date.data,
            description=form.description.data
        )
        db.session.add(advance)
        db.session.commit()
        flash('Salary advance recorded!', 'success')
        return redirect(url_for('salary.advance_list'))
    return render_template('salary/advance_form.html', form=form, title="Record Advance")

@bp.route('/advances/delete/<int:id>', methods=['POST'])
@login_required
def delete_advance(id):
    advance = SalaryAdvance.query.get_or_404(id)
    if advance.is_deducted:
        flash('Cannot delete a deducted advance. Delete the salary payment first.', 'danger')
        return redirect(url_for('salary.advance_list'))
    db.session.delete(advance)
    db.session.commit()
    flash('Salary advance deleted.', 'info')
    return redirect(url_for('salary.advance_list'))

# --- Salary Payments ---

@bp.route('/payments')
@login_required
def payment_list():
    payments = SalaryPayment.query.order_by(SalaryPayment.year.desc(), SalaryPayment.month.desc()).all()
    return render_template('salary/payment_list.html', payments=payments)

@bp.route('/payments/process', methods=['GET', 'POST'])
@login_required
def process_salary_select():
    staff_members = Staff.query.filter_by(is_active=True).all()
    return render_template('salary/process_salary_select.html', staff_members=staff_members)

@bp.route('/payments/pay/<int:staff_id>', methods=['GET', 'POST'])
@login_required
def pay_salary(staff_id):
    staff = Staff.query.get_or_404(staff_id)
    form = SalaryPaymentForm()
    form.staff_id.choices = [(staff.id, staff.name)]
    
    # Pre-fill data
    if request.method == 'GET':
        form.staff_id.data = staff.id
        form.base_salary.data = staff.monthly_salary
        form.month.data = datetime.utcnow().month
        form.year.data = datetime.utcnow().year
        form.payment_date.data = datetime.utcnow().date()
        
        # Calculate outstanding advances
        outstanding_advances = SalaryAdvance.query.filter_by(staff_id=staff.id, is_deducted=False).all()
        form.advance_deduction.data = sum(a.amount for a in outstanding_advances)

    if form.validate_on_submit():
        print(f"Form validated for {staff.name}")
        # Check if already paid for this month/year
        existing = SalaryPayment.query.filter_by(staff_id=staff.id, month=form.month.data, year=form.year.data).first()
        if existing:
            flash(f'Salary already processed for {staff.name} for {form.month.data}/{form.year.data}', 'warning')
            return redirect(url_for('salary.payment_list'))

        net_salary = form.base_salary.data + form.bonus.data - form.advance_deduction.data - form.other_deductions.data
        
        payment = SalaryPayment(
            staff_id=staff.id,
            month=form.month.data,
            year=form.year.data,
            base_salary=form.base_salary.data,
            advance_deduction=form.advance_deduction.data,
            bonus=form.bonus.data,
            other_deductions=form.other_deductions.data,
            net_salary=net_salary,
            payment_date=form.payment_date.data,
            payment_method=form.payment_method.data,
            status=form.status.data,
            notes=form.notes.data
        )
        db.session.add(payment)
        db.session.flush() # Get payment.id

        # Mark advances as deducted
        if form.advance_deduction.data > 0:
            unpaid_advances = SalaryAdvance.query.filter_by(staff_id=staff.id, is_deducted=False).order_by(SalaryAdvance.date.asc()).all()
            deducted_so_far = 0
            for adv in unpaid_advances:
                if deducted_so_far < form.advance_deduction.data:
                    adv.is_deducted = True
                    adv.salary_payment_id = payment.id
                    deducted_so_far += adv.amount
        
        db.session.commit()
        flash(f'Salary processed for {staff.name}', 'success')
        return redirect(url_for('salary.payment_list'))

    return render_template('salary/pay_form.html', form=form, staff=staff)

@bp.route('/payments/delete/<int:id>', methods=['POST'])
@login_required
def delete_payment(id):
    payment = SalaryPayment.query.get_or_404(id)
    # Revert advances
    for advance in payment.deducted_advances:
        advance.is_deducted = False
        advance.salary_payment_id = None
    
    db.session.delete(payment)
    db.session.commit()
    flash('Salary payment deleted and advances reverted.', 'info')
    return redirect(url_for('salary.payment_list'))

# --- API for dynamic updates ---
@bp.route('/api/get_staff_info/<int:staff_id>')
@login_required
def get_staff_info(staff_id):
    staff = Staff.query.get_or_404(staff_id)
    outstanding_advance = sum(a.amount for a in staff.advances if not a.is_deducted)
    return jsonify({
        'monthly_salary': staff.monthly_salary,
        'outstanding_advance': outstanding_advance
    })
