from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from app.utils import permission_required
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
        # Handle empty email - DB requires it to be non-null and unique
        user_email = form.email.data
        if not user_email or not user_email.strip():
            user_email = f"{form.username.data.lower()}@noemail.local"
        else:
            if User.query.filter_by(email=user_email).first():
                flash('Email already exists.', 'danger')
                return render_template('users/create.html', form=form)
            
        user = User(
            username=form.username.data,
            email=user_email,
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
            can_view_accounting=form.can_view_accounting.data,
            can_view_salesmen=form.can_view_salesmen.data,
            can_view_product_dev=form.can_view_product_dev.data,
            can_view_categories=form.can_view_categories.data,
            can_view_customer_groups=form.can_view_customer_groups.data,
            can_view_tasks=form.can_view_tasks.data,
            can_view_profit_loss=form.can_view_profit_loss.data,
            can_view_users=form.can_view_users.data,
            can_add_sales=form.can_add_sales.data,
            can_add_purchases=form.can_add_purchases.data,
            can_add_inventory=form.can_add_inventory.data,
            can_add_expenses=form.can_add_expenses.data,
            can_add_returns=form.can_add_returns.data,
            can_add_vendors=form.can_add_vendors.data,
            can_add_customers=form.can_add_customers.data,
            can_add_reports=form.can_add_reports.data,
            can_add_settings=form.can_add_settings.data,
            can_add_manufacturing=form.can_add_manufacturing.data,
            can_add_production=form.can_add_production.data,
            can_add_warehouse=form.can_add_warehouse.data,
            can_add_attendance=form.can_add_attendance.data,
            can_add_salary=form.can_add_salary.data,
            can_add_targets=form.can_add_targets.data,
            can_add_dashboard=form.can_add_dashboard.data,
            can_add_accounting=form.can_add_accounting.data,
            can_add_salesmen=form.can_add_salesmen.data,
            can_add_product_dev=form.can_add_product_dev.data,
            can_add_categories=form.can_add_categories.data,
            can_add_customer_groups=form.can_add_customer_groups.data,
            can_add_tasks=form.can_add_tasks.data,
            can_add_profit_loss=form.can_add_profit_loss.data,
            can_add_users=form.can_add_users.data,
            can_edit_sales=form.can_edit_sales.data,
            can_edit_purchases=form.can_edit_purchases.data,
            can_edit_inventory=form.can_edit_inventory.data,
            can_edit_expenses=form.can_edit_expenses.data,
            can_edit_returns=form.can_edit_returns.data,
            can_edit_vendors=form.can_edit_vendors.data,
            can_edit_customers=form.can_edit_customers.data,
            can_edit_reports=form.can_edit_reports.data,
            can_edit_settings=form.can_edit_settings.data,
            can_edit_manufacturing=form.can_edit_manufacturing.data,
            can_edit_production=form.can_edit_production.data,
            can_edit_warehouse=form.can_edit_warehouse.data,
            can_edit_attendance=form.can_edit_attendance.data,
            can_edit_salary=form.can_edit_salary.data,
            can_edit_targets=form.can_edit_targets.data,
            can_edit_dashboard=form.can_edit_dashboard.data,
            can_edit_accounting=form.can_edit_accounting.data,
            can_edit_salesmen=form.can_edit_salesmen.data,
            can_edit_product_dev=form.can_edit_product_dev.data,
            can_edit_categories=form.can_edit_categories.data,
            can_edit_customer_groups=form.can_edit_customer_groups.data,
            can_edit_tasks=form.can_edit_tasks.data,
            can_edit_profit_loss=form.can_edit_profit_loss.data,
            can_edit_users=form.can_edit_users.data,
            can_delete_sales=form.can_delete_sales.data,
            can_delete_purchases=form.can_delete_purchases.data,
            can_delete_inventory=form.can_delete_inventory.data,
            can_delete_expenses=form.can_delete_expenses.data,
            can_delete_returns=form.can_delete_returns.data,
            can_delete_vendors=form.can_delete_vendors.data,
            can_delete_customers=form.can_delete_customers.data,
            can_delete_reports=form.can_delete_reports.data,
            can_delete_settings=form.can_delete_settings.data,
            can_delete_manufacturing=form.can_delete_manufacturing.data,
            can_delete_production=form.can_delete_production.data,
            can_delete_warehouse=form.can_delete_warehouse.data,
            can_delete_attendance=form.can_delete_attendance.data,
            can_delete_salary=form.can_delete_salary.data,
            can_delete_targets=form.can_delete_targets.data,
            can_delete_dashboard=form.can_delete_dashboard.data,
            can_delete_accounting=form.can_delete_accounting.data,
            can_delete_salesmen=form.can_delete_salesmen.data,
            can_delete_product_dev=form.can_delete_product_dev.data,
            can_delete_categories=form.can_delete_categories.data,
            can_delete_customer_groups=form.can_delete_customer_groups.data,
            can_delete_tasks=form.can_delete_tasks.data,
            can_delete_profit_loss=form.can_delete_profit_loss.data,
            can_delete_users=form.can_delete_users.data,
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
        user_email = form.email.data
        if not user_email or not user_email.strip():
            user_email = f"{user.username.lower()}_at_noemail.local"
            
        user.email = user_email
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
        user.can_view_salesmen = form.can_view_salesmen.data
        user.can_view_product_dev = form.can_view_product_dev.data
        user.can_view_categories = form.can_view_categories.data
        user.can_view_customer_groups = form.can_view_customer_groups.data
        user.can_view_tasks = form.can_view_tasks.data
        user.can_view_profit_loss = form.can_view_profit_loss.data
        user.can_view_users = form.can_view_users.data
        user.can_add_sales = form.can_add_sales.data
        user.can_add_purchases = form.can_add_purchases.data
        user.can_add_inventory = form.can_add_inventory.data
        user.can_add_expenses = form.can_add_expenses.data
        user.can_add_returns = form.can_add_returns.data
        user.can_add_vendors = form.can_add_vendors.data
        user.can_add_customers = form.can_add_customers.data
        user.can_add_reports = form.can_add_reports.data
        user.can_add_settings = form.can_add_settings.data
        user.can_add_manufacturing = form.can_add_manufacturing.data
        user.can_add_production = form.can_add_production.data
        user.can_add_warehouse = form.can_add_warehouse.data
        user.can_add_attendance = form.can_add_attendance.data
        user.can_add_salary = form.can_add_salary.data
        user.can_add_targets = form.can_add_targets.data
        user.can_add_dashboard = form.can_add_dashboard.data
        user.can_add_accounting = form.can_add_accounting.data
        user.can_add_salesmen = form.can_add_salesmen.data
        user.can_add_product_dev = form.can_add_product_dev.data
        user.can_add_categories = form.can_add_categories.data
        user.can_add_customer_groups = form.can_add_customer_groups.data
        user.can_add_tasks = form.can_add_tasks.data
        user.can_add_profit_loss = form.can_add_profit_loss.data
        user.can_add_users = form.can_add_users.data
        user.can_edit_sales = form.can_edit_sales.data
        user.can_edit_purchases = form.can_edit_purchases.data
        user.can_edit_inventory = form.can_edit_inventory.data
        user.can_edit_expenses = form.can_edit_expenses.data
        user.can_edit_returns = form.can_edit_returns.data
        user.can_edit_vendors = form.can_edit_vendors.data
        user.can_edit_customers = form.can_edit_customers.data
        user.can_edit_reports = form.can_edit_reports.data
        user.can_edit_settings = form.can_edit_settings.data
        user.can_edit_manufacturing = form.can_edit_manufacturing.data
        user.can_edit_production = form.can_edit_production.data
        user.can_edit_warehouse = form.can_edit_warehouse.data
        user.can_edit_attendance = form.can_edit_attendance.data
        user.can_edit_salary = form.can_edit_salary.data
        user.can_edit_targets = form.can_edit_targets.data
        user.can_edit_dashboard = form.can_edit_dashboard.data
        user.can_edit_accounting = form.can_edit_accounting.data
        user.can_edit_salesmen = form.can_edit_salesmen.data
        user.can_edit_product_dev = form.can_edit_product_dev.data
        user.can_edit_categories = form.can_edit_categories.data
        user.can_edit_customer_groups = form.can_edit_customer_groups.data
        user.can_edit_tasks = form.can_edit_tasks.data
        user.can_edit_profit_loss = form.can_edit_profit_loss.data
        user.can_edit_users = form.can_edit_users.data
        user.can_delete_sales = form.can_delete_sales.data
        user.can_delete_purchases = form.can_delete_purchases.data
        user.can_delete_inventory = form.can_delete_inventory.data
        user.can_delete_expenses = form.can_delete_expenses.data
        user.can_delete_returns = form.can_delete_returns.data
        user.can_delete_vendors = form.can_delete_vendors.data
        user.can_delete_customers = form.can_delete_customers.data
        user.can_delete_reports = form.can_delete_reports.data
        user.can_delete_settings = form.can_delete_settings.data
        user.can_delete_manufacturing = form.can_delete_manufacturing.data
        user.can_delete_production = form.can_delete_production.data
        user.can_delete_warehouse = form.can_delete_warehouse.data
        user.can_delete_attendance = form.can_delete_attendance.data
        user.can_delete_salary = form.can_delete_salary.data
        user.can_delete_targets = form.can_delete_targets.data
        user.can_delete_dashboard = form.can_delete_dashboard.data
        user.can_delete_accounting = form.can_delete_accounting.data
        user.can_delete_salesmen = form.can_delete_salesmen.data
        user.can_delete_product_dev = form.can_delete_product_dev.data
        user.can_delete_categories = form.can_delete_categories.data
        user.can_delete_customer_groups = form.can_delete_customer_groups.data
        user.can_delete_tasks = form.can_delete_tasks.data
        user.can_delete_profit_loss = form.can_delete_profit_loss.data
        user.can_delete_users = form.can_delete_users.data
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
        form.can_view_salesmen.data = getattr(user, 'can_view_salesmen', True)
        form.can_view_product_dev.data = getattr(user, 'can_view_product_dev', True)
        form.can_view_categories.data = getattr(user, 'can_view_categories', True)
        form.can_view_customer_groups.data = getattr(user, 'can_view_customer_groups', True)
        form.can_view_tasks.data = getattr(user, 'can_view_tasks', True)
        form.can_view_profit_loss.data = getattr(user, 'can_view_profit_loss', True)
        form.can_view_users.data = getattr(user, 'can_view_users', False)
        form.can_add_sales.data = getattr(user, 'can_add_sales', False)
        form.can_add_purchases.data = getattr(user, 'can_add_purchases', False)
        form.can_add_inventory.data = getattr(user, 'can_add_inventory', False)
        form.can_add_expenses.data = getattr(user, 'can_add_expenses', False)
        form.can_add_returns.data = getattr(user, 'can_add_returns', False)
        form.can_add_vendors.data = getattr(user, 'can_add_vendors', False)
        form.can_add_customers.data = getattr(user, 'can_add_customers', False)
        form.can_add_reports.data = getattr(user, 'can_add_reports', False)
        form.can_add_settings.data = getattr(user, 'can_add_settings', False)
        form.can_add_manufacturing.data = getattr(user, 'can_add_manufacturing', False)
        form.can_add_production.data = getattr(user, 'can_add_production', False)
        form.can_add_warehouse.data = getattr(user, 'can_add_warehouse', False)
        form.can_add_attendance.data = getattr(user, 'can_add_attendance', False)
        form.can_add_salary.data = getattr(user, 'can_add_salary', False)
        form.can_add_targets.data = getattr(user, 'can_add_targets', False)
        form.can_add_dashboard.data = getattr(user, 'can_add_dashboard', False)
        form.can_add_accounting.data = getattr(user, 'can_add_accounting', False)
        form.can_add_salesmen.data = getattr(user, 'can_add_salesmen', False)
        form.can_add_product_dev.data = getattr(user, 'can_add_product_dev', False)
        form.can_add_categories.data = getattr(user, 'can_add_categories', False)
        form.can_add_customer_groups.data = getattr(user, 'can_add_customer_groups', False)
        form.can_add_tasks.data = getattr(user, 'can_add_tasks', False)
        form.can_add_profit_loss.data = getattr(user, 'can_add_profit_loss', False)
        form.can_add_users.data = getattr(user, 'can_add_users', False)
        form.can_edit_sales.data = getattr(user, 'can_edit_sales', False)
        form.can_edit_purchases.data = getattr(user, 'can_edit_purchases', False)
        form.can_edit_inventory.data = getattr(user, 'can_edit_inventory', False)
        form.can_edit_expenses.data = getattr(user, 'can_edit_expenses', False)
        form.can_edit_returns.data = getattr(user, 'can_edit_returns', False)
        form.can_edit_vendors.data = getattr(user, 'can_edit_vendors', False)
        form.can_edit_customers.data = getattr(user, 'can_edit_customers', False)
        form.can_edit_reports.data = getattr(user, 'can_edit_reports', False)
        form.can_edit_settings.data = getattr(user, 'can_edit_settings', False)
        form.can_edit_manufacturing.data = getattr(user, 'can_edit_manufacturing', False)
        form.can_edit_production.data = getattr(user, 'can_edit_production', False)
        form.can_edit_warehouse.data = getattr(user, 'can_edit_warehouse', False)
        form.can_edit_attendance.data = getattr(user, 'can_edit_attendance', False)
        form.can_edit_salary.data = getattr(user, 'can_edit_salary', False)
        form.can_edit_targets.data = getattr(user, 'can_edit_targets', False)
        form.can_edit_dashboard.data = getattr(user, 'can_edit_dashboard', False)
        form.can_edit_accounting.data = getattr(user, 'can_edit_accounting', False)
        form.can_edit_salesmen.data = getattr(user, 'can_edit_salesmen', False)
        form.can_edit_product_dev.data = getattr(user, 'can_edit_product_dev', False)
        form.can_edit_categories.data = getattr(user, 'can_edit_categories', False)
        form.can_edit_customer_groups.data = getattr(user, 'can_edit_customer_groups', False)
        form.can_edit_tasks.data = getattr(user, 'can_edit_tasks', False)
        form.can_edit_profit_loss.data = getattr(user, 'can_edit_profit_loss', False)
        form.can_edit_users.data = getattr(user, 'can_edit_users', False)
        form.can_delete_sales.data = getattr(user, 'can_delete_sales', False)
        form.can_delete_purchases.data = getattr(user, 'can_delete_purchases', False)
        form.can_delete_inventory.data = getattr(user, 'can_delete_inventory', False)
        form.can_delete_expenses.data = getattr(user, 'can_delete_expenses', False)
        form.can_delete_returns.data = getattr(user, 'can_delete_returns', False)
        form.can_delete_vendors.data = getattr(user, 'can_delete_vendors', False)
        form.can_delete_customers.data = getattr(user, 'can_delete_customers', False)
        form.can_delete_reports.data = getattr(user, 'can_delete_reports', False)
        form.can_delete_settings.data = getattr(user, 'can_delete_settings', False)
        form.can_delete_manufacturing.data = getattr(user, 'can_delete_manufacturing', False)
        form.can_delete_production.data = getattr(user, 'can_delete_production', False)
        form.can_delete_warehouse.data = getattr(user, 'can_delete_warehouse', False)
        form.can_delete_attendance.data = getattr(user, 'can_delete_attendance', False)
        form.can_delete_salary.data = getattr(user, 'can_delete_salary', False)
        form.can_delete_targets.data = getattr(user, 'can_delete_targets', False)
        form.can_delete_dashboard.data = getattr(user, 'can_delete_dashboard', False)
        form.can_delete_accounting.data = getattr(user, 'can_delete_accounting', False)
        form.can_delete_salesmen.data = getattr(user, 'can_delete_salesmen', False)
        form.can_delete_product_dev.data = getattr(user, 'can_delete_product_dev', False)
        form.can_delete_categories.data = getattr(user, 'can_delete_categories', False)
        form.can_delete_customer_groups.data = getattr(user, 'can_delete_customer_groups', False)
        form.can_delete_tasks.data = getattr(user, 'can_delete_tasks', False)
        form.can_delete_profit_loss.data = getattr(user, 'can_delete_profit_loss', False)
        form.can_delete_users.data = getattr(user, 'can_delete_users', False)
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
@permission_required('users', action='edit')
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
