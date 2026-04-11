from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import User, Task
from app.forms import UserForm, UserEditForm, TaskForm
from datetime import datetime
from functools import wraps

bp = Blueprint('users', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

# User Management Routes
@bp.route('/list')
@login_required
@admin_required
def list_users():
    users = User.query.all()
    return render_template('users/index.html', users=users)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = UserForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists.', 'danger')
            return render_template('users/create.html', form=form)
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already exists.', 'danger')
            return render_template('users/create.html', form=form)
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data,
            is_active=(form.is_active.data if form.is_active.data is not None else True),
            can_view_sales=form.can_view_sales.data,
            can_view_purchases=form.can_view_purchases.data,
            can_view_inventory=form.can_view_inventory.data,
            can_view_expenses=form.can_view_expenses.data,
            can_view_returns=form.can_view_returns.data,
            can_view_vendors=form.can_view_vendors.data,
            can_view_customers=form.can_view_customers.data,
            can_view_reports=form.can_view_reports.data,
            can_view_settings=form.can_view_settings.data,
            can_view_manufacturing=form.can_view_manufacturing.data,
            can_view_production=form.can_view_production.data,
            can_view_warehouse=form.can_view_warehouse.data,
            can_view_attendance=form.can_view_attendance.data,
            can_view_salary=form.can_view_salary.data,
            can_view_targets=form.can_view_targets.data,
            can_view_dashboard=form.can_view_dashboard.data,
            can_view_accounting=form.can_view_accounting.data
        )
        # Set password - form is now required to have a password
        if form.password.data and form.password.data.strip():
            user.set_password(form.password.data)
        else:
            user.set_password('password123')  # Fallback only if form somehow passes empty
        db.session.add(user)
        db.session.commit()
        flash(f'User "{user.username}" created successfully with password: {form.password.data or "password123"}', 'success')
        return redirect(url_for('users.list_users'))
    return render_template('users/create.html', form=form)

@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    form = UserEditForm()
    if form.validate_on_submit():
        # Username is not editable, keep original
        user.email = form.email.data
        user.role = form.role.data
        user.is_active = form.is_active.data
        user.can_view_sales = form.can_view_sales.data
        user.can_view_purchases = form.can_view_purchases.data
        user.can_view_inventory = form.can_view_inventory.data
        user.can_view_expenses = form.can_view_expenses.data
        user.can_view_returns = form.can_view_returns.data
        user.can_view_vendors = form.can_view_vendors.data
        user.can_view_customers = form.can_view_customers.data
        user.can_view_reports = form.can_view_reports.data
        user.can_view_settings = form.can_view_settings.data
        user.can_view_manufacturing = form.can_view_manufacturing.data
        user.can_view_production = form.can_view_production.data
        user.can_view_warehouse = form.can_view_warehouse.data
        user.can_view_attendance = form.can_view_attendance.data
        user.can_view_salary = form.can_view_salary.data
        user.can_view_targets = form.can_view_targets.data
        user.can_view_dashboard = form.can_view_dashboard.data
        user.can_view_accounting = form.can_view_accounting.data
        if form.password.data and form.password.data.strip():
            user.set_password(form.password.data)
        db.session.commit()
        flash('User updated successfully.', 'success')
        return redirect(url_for('users.list_users'))
    elif request.method == 'GET':
        form.email.data = user.email
        form.role.data = user.role
        form.is_active.data = 'True' if user.is_active else 'False'
        form.can_view_sales.data = user.can_view_sales
        form.can_view_purchases.data = user.can_view_purchases
        form.can_view_inventory.data = user.can_view_inventory
        form.can_view_expenses.data = user.can_view_expenses
        form.can_view_returns.data = user.can_view_returns
        form.can_view_vendors.data = user.can_view_vendors
        form.can_view_customers.data = user.can_view_customers
        form.can_view_reports.data = user.can_view_reports
        form.can_view_settings.data = user.can_view_settings
        form.can_view_manufacturing.data = getattr(user, 'can_view_manufacturing', True)
        form.can_view_production.data = getattr(user, 'can_view_production', True)
        form.can_view_warehouse.data = getattr(user, 'can_view_warehouse', True)
        form.can_view_attendance.data = getattr(user, 'can_view_attendance', True)
        form.can_view_salary.data = getattr(user, 'can_view_salary', True)
        form.can_view_targets.data = getattr(user, 'can_view_targets', True)
        form.can_view_dashboard.data = getattr(user, 'can_view_dashboard', True)
        form.can_view_accounting.data = getattr(user, 'can_view_accounting', True)
    return render_template('users/edit.html', form=form, user=user)

# Task Management Routes
@bp.route('/tasks')
@login_required
def list_tasks():
    if current_user.role == 'admin':
        tasks = Task.query.all()
    else:
        tasks = Task.query.filter_by(assigned_to_id=current_user.id).all()
    return render_template('tasks/index.html', tasks=tasks)

@bp.route('/tasks/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_task():
    form = TaskForm()
    # Populate users for assignment
    form.assigned_to_id.choices = [(u.id, f"{u.username} ({u.role})") for u in User.query.all()]
    
    if form.validate_on_submit():
        task = Task(
            title=form.title.data,
            description=form.description.data,
            priority=form.priority.data,
            status=form.status.data,
            due_date=form.due_date.data,
            assigned_to_id=form.assigned_to_id.data,
            created_by_id=current_user.id
        )
        db.session.add(task)
        db.session.commit()
        flash('Task assigned successfully.', 'success')
        return redirect(url_for('users.list_tasks'))
    return render_template('tasks/create.html', form=form)

@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    
    # Prevent deleting the current logged-in user
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('users.list_users'))
    
    # Prevent deleting users that don't meet deletion criteria
    if user.role != 'user' and user.is_active:
        flash(f'Cannot delete active {user.role} users. Please mark them as inactive first.', 'danger')
        return redirect(url_for('users.list_users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{username}" has been deleted successfully.', 'success')
    return redirect(url_for('users.list_users'))

@bp.route('/tasks/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_task(id):
    task = Task.query.get_or_404(id)
    task_title = task.title
    db.session.delete(task)
    db.session.commit()
    flash(f'Task "{task_title}" has been deleted successfully.', 'success')
    return redirect(url_for('users.list_tasks'))

@bp.route('/update-task-status/<int:id>', methods=['POST'])
@login_required
def update_task_status(id):
    task = Task.query.get_or_404(id)
    # Check if user is admin or the assigned user
    if current_user.role != 'admin' and task.assigned_to_id != current_user.id:
        abort(403)
    
    new_status = request.form.get('status')
    if new_status in ['Pending', 'In Progress', 'Completed', 'Cancelled']:
        task.status = new_status
        db.session.commit()
        flash(f'Task status updated to {new_status}.', 'success')
    return redirect(url_for('users.list_tasks'))
