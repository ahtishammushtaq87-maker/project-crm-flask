from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from app.utils import permission_required, log_activity, pk_now
from flask_login import login_required, current_user
from app import db
from app.models import User, Task, TaskSettings, Sale, TaskGroup
from app.forms import UserForm, UserEditForm, TaskForm, TaskSettingsForm
from app.services.mail_service import send_task_email
from datetime import datetime, date
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
            can_view_receiving=form.can_view_receiving.data,
            can_view_delivering=form.can_view_delivering.data,
            can_view_media=form.can_view_media.data,
            can_view_media_document=form.can_view_media_document.data,
            can_view_activity_logs=form.can_view_activity_logs.data,
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
            can_add_receiving=form.can_add_receiving.data,
            can_add_delivering=form.can_add_delivering.data,
            can_add_media=form.can_add_media.data,
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
            can_edit_receiving=form.can_edit_receiving.data,
            can_edit_delivering=form.can_edit_delivering.data,
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
            can_delete_receiving=form.can_delete_receiving.data,
            can_delete_delivering=form.can_delete_delivering.data,
            can_delete_media=form.can_delete_media.data,
            can_delete_activity_logs=form.can_delete_activity_logs.data,
            can_view_recovery=form.can_view_recovery.data,
            can_add_recovery=form.can_add_recovery.data,
            can_edit_recovery=form.can_edit_recovery.data,
            can_delete_recovery=form.can_delete_recovery.data,
            can_view_quotations=form.can_view_quotations.data,
            can_add_quotations=form.can_add_quotations.data,
            can_edit_quotations=form.can_edit_quotations.data,
            can_delete_quotations=form.can_delete_quotations.data,
        )
        # Set password - form is now required to have a password
        if form.password.data and form.password.data.strip():
            user.set_password(form.password.data)
        else:
            user.set_password('password123')  # Fallback only if form somehow passes empty
        db.session.add(user)
        db.session.commit()
        
        log_activity('Users', f'Created User: {user.username}', f'Role: {user.role}, Email: {user.email}')
        
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
        user.can_view_receiving = form.can_view_receiving.data
        user.can_view_delivering = form.can_view_delivering.data
        user.can_view_media = form.can_view_media.data
        user.can_view_media_document = form.can_view_media_document.data
        user.can_view_activity_logs = form.can_view_activity_logs.data
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
        user.can_add_receiving = form.can_add_receiving.data
        user.can_add_delivering = form.can_add_delivering.data
        user.can_add_media = form.can_add_media.data
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
        user.can_edit_receiving = form.can_edit_receiving.data
        user.can_edit_delivering = form.can_edit_delivering.data
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
        user.can_delete_receiving = form.can_delete_receiving.data
        user.can_delete_delivering = form.can_delete_delivering.data
        user.can_delete_media = form.can_delete_media.data
        user.can_delete_activity_logs = form.can_delete_activity_logs.data
        user.can_view_recovery = form.can_view_recovery.data
        user.can_add_recovery = form.can_add_recovery.data
        user.can_edit_recovery = form.can_edit_recovery.data
        user.can_delete_recovery = form.can_delete_recovery.data
        user.can_view_quotations = form.can_view_quotations.data
        user.can_add_quotations = form.can_add_quotations.data
        user.can_edit_quotations = form.can_edit_quotations.data
        user.can_delete_quotations = form.can_delete_quotations.data
        if form.password.data and form.password.data.strip():
            user.set_password(form.password.data)
        db.session.commit()
        
        log_activity('Users', f'Updated User: {user.username}', f'Role: {user.role}, Active: {user.is_active}')
        
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
        form.can_view_receiving.data = getattr(user, 'can_view_receiving', False)
        form.can_view_delivering.data = getattr(user, 'can_view_delivering', False)
        form.can_view_media.data = getattr(user, 'can_view_media', True)
        form.can_view_media_document.data = getattr(user, 'can_view_media_document', False)
        form.can_view_activity_logs.data = getattr(user, 'can_view_activity_logs', False)
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
        form.can_add_receiving.data = getattr(user, 'can_add_receiving', False)
        form.can_add_delivering.data = getattr(user, 'can_add_delivering', False)
        form.can_add_media.data = getattr(user, 'can_add_media', False)
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
        form.can_edit_receiving.data = getattr(user, 'can_edit_receiving', False)
        form.can_edit_delivering.data = getattr(user, 'can_edit_delivering', False)
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
        form.can_delete_receiving.data = getattr(user, 'can_delete_receiving', False)
        form.can_delete_delivering.data = getattr(user, 'can_delete_delivering', False)
        form.can_delete_media.data = getattr(user, 'can_delete_media', False)
        form.can_delete_activity_logs.data = getattr(user, 'can_delete_activity_logs', False)
        form.can_view_recovery.data = getattr(user, 'can_view_recovery', True)
        form.can_add_recovery.data = getattr(user, 'can_add_recovery', False)
        form.can_edit_recovery.data = getattr(user, 'can_edit_recovery', False)
        form.can_delete_recovery.data = getattr(user, 'can_delete_recovery', False)
        form.can_view_quotations.data = getattr(user, 'can_view_quotations', True)
        form.can_add_quotations.data = getattr(user, 'can_add_quotations', False)
        form.can_edit_quotations.data = getattr(user, 'can_edit_quotations', False)
        form.can_delete_quotations.data = getattr(user, 'can_delete_quotations', False)
    return render_template('users/edit.html', form=form, user=user)

# Task Management Routes
@bp.route('/tasks')
@login_required
def list_tasks():
    # ── Filters ────────────────────────────────────────────────────────
    group_filter = request.args.get('group', '').strip()
    invoice_id = request.args.get('invoice_id', '').strip()
    
    # Recovery popup reminders (Sales Recovery module) are a separate, auto-
    # managed concept — they must not appear in the general Tasks list.
    query = Task.query.filter(Task.recovery_task_id.is_(None))
    if current_user.role != 'admin':
        query = query.filter_by(assigned_to_id=current_user.id)

    if group_filter:
        query = query.filter_by(task_group_name=group_filter)
    if invoice_id:
        query = query.filter_by(linked_invoice_id=invoice_id)
        
    tasks = query.order_by(Task.reminder_at.desc()).all()
    # ───────────────────────────────────────────────────────────────────

    task_groups = TaskGroup.query.order_by(TaskGroup.name).all()
    
    # Get unique linked invoices that exist in tasks for the filter dropdown
    # (excluding recovery reminders, which aren't shown in this list either)
    linked_invoice_ids = db.session.query(Task.linked_invoice_id).filter(
        Task.linked_invoice_id != None, Task.recovery_task_id.is_(None)
    ).distinct().all()
    unique_ids = [i[0] for i in linked_invoice_ids]
    linked_invoices = Sale.query.filter(Sale.id.in_(unique_ids)).order_by(Sale.invoice_number.desc()).all() if unique_ids else []

    from flask_wtf.csrf import generate_csrf
    return render_template('tasks/index.html', 
                         tasks=tasks, 
                         task_groups=task_groups,
                         linked_invoices=linked_invoices,
                         group_filter=group_filter,
                         invoice_filter_id=invoice_id,
                         csrf_token_value=generate_csrf())

@bp.route('/tasks/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_task():
    form = TaskForm()
    # Populate users for assignment
    form.assigned_to_id.choices = [(u.id, f"{u.username} ({u.role})") for u in User.query.all()]

    # Populate overdue invoices dropdown
    today = date.today()
    overdue_sales = Sale.query.filter(
        Sale.status != 'paid',
        Sale.due_date != None,
        Sale.due_date < datetime.combine(today, datetime.min.time())
    ).order_by(Sale.due_date.asc()).all()
    invoice_choices = [(0, '— None —')] + [
        (s.id, f"{s.invoice_number} | {s.customer.name if s.customer else 'N/A'} | Due: {s.due_date.strftime('%Y-%m-%d') if s.due_date else ''}")
        for s in overdue_sales
    ]
    form.linked_invoice_id.choices = invoice_choices

    # Collect existing group names for autocomplete suggestions
    existing_groups = db.session.query(Task.task_group_name).filter(
        Task.task_group_name != None, Task.task_group_name != ''
    ).distinct().all()
    group_suggestions = [g[0] for g in existing_groups]
    
    if form.validate_on_submit():
        linked_inv = form.linked_invoice_id.data if form.linked_invoice_id.data else None
        task = Task(
            title=form.title.data,
            description=form.description.data,
            priority=form.priority.data,
            status=form.status.data,
            reminder_at=form.reminder_at.data,
            assigned_to_id=form.assigned_to_id.data,
            created_by_id=current_user.id,
            task_group_name=form.task_group_name.data.strip() if form.task_group_name.data else None,
            linked_invoice_id=linked_inv
        )
        db.session.add(task)
        db.session.commit()
        
        log_activity('Tasks', f'Created Task: {task.title}', f'Assigned to: {task.assigned_to.username}, Priority: {task.priority}')
        
        flash('Task assigned successfully.', 'success')
        return redirect(url_for('users.list_tasks'))
    task_groups = TaskGroup.query.order_by(TaskGroup.name).all()
    return render_template('tasks/create.html', form=form, task_groups=task_groups, overdue_sales=overdue_sales)

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
    
    log_activity('Users', f'Deleted User: {username}', 'User account removed from system')
    
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
    
    log_activity('Tasks', f'Deleted Task: {task_title}', f'Removed task: {task_title}')
    
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

@bp.route('/tasks/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_task(id):
    task = Task.query.get_or_404(id)
    form = TaskForm(obj=task)
    form.assigned_to_id.choices = [(u.id, f"{u.username} ({u.role})") for u in User.query.all()]

    # Populate overdue invoices dropdown
    today = date.today()
    overdue_sales = Sale.query.filter(
        Sale.status != 'paid',
        Sale.due_date != None,
        Sale.due_date < datetime.combine(today, datetime.min.time())
    ).order_by(Sale.due_date.asc()).all()
    invoice_choices = [(0, '— None —')] + [
        (s.id, f"{s.invoice_number} | {s.customer.name if s.customer else 'N/A'} | Due: {s.due_date.strftime('%Y-%m-%d') if s.due_date else ''}")
        for s in overdue_sales
    ]
    # If the task's linked invoice is not in overdue list (e.g. it was paid), still include it
    if task.linked_invoice_id and task.linked_invoice_id not in [c[0] for c in invoice_choices]:
        if task.linked_invoice:
            inv = task.linked_invoice
            invoice_choices.append((inv.id, f"{inv.invoice_number} | {inv.customer.name if inv.customer else 'N/A'} (was linked)"))
    form.linked_invoice_id.choices = invoice_choices

    # Collect existing group names for autocomplete suggestions
    existing_groups = db.session.query(Task.task_group_name).filter(
        Task.task_group_name != None, Task.task_group_name != ''
    ).distinct().all()
    group_suggestions = [g[0] for g in existing_groups]
    
    if form.validate_on_submit():
        task.title = form.title.data
        task.description = form.description.data
        task.priority = form.priority.data
        task.status = form.status.data
        task.reminder_at = form.reminder_at.data
        task.assigned_to_id = form.assigned_to_id.data
        task.task_group_name = form.task_group_name.data.strip() if form.task_group_name.data else None
        task.linked_invoice_id = form.linked_invoice_id.data if form.linked_invoice_id.data else None
        
        # Reset notification shown if reminder time changed and is in future
        if task.reminder_at and task.reminder_at > datetime.utcnow():
            task.is_notification_shown = False
            
        db.session.commit()
        log_activity('Tasks', f'Updated Task: {task.title}', f'Assigned to: {task.assigned_to.username}')
        flash('Task updated successfully.', 'success')
        return redirect(url_for('users.list_tasks'))
        
    task_groups = TaskGroup.query.order_by(TaskGroup.name).all()
    return render_template('tasks/edit.html', form=form, task=task, task_groups=task_groups, overdue_sales=overdue_sales)

@bp.route('/tasks/poll')
@login_required
def poll_tasks():
    # Only poll for current user's assigned tasks
    client_time_str = request.args.get('client_time')
    if client_time_str:
        try:
            # client_time is sent as a local ISO-like string: YYYY-MM-DDTHH:MM:SS.sss
            # We strip any zone info if present and parse as naive to match DB format
            clean_time = client_time_str.split('Z')[0].split('+')[0]
            now = datetime.fromisoformat(clean_time)
        except Exception as e:
            print(f"Error parsing client_time: {e}")
            now = pk_now()
    else:
        now = pk_now()

    due_tasks = Task.query.filter(
        Task.assigned_to_id == current_user.id,
        Task.reminder_at <= now,
        Task.is_notification_shown == False,
        Task.status.in_(['Pending', 'In Progress'])
    ).all()
    
    CLOSED_RECOVERY = ('CLOSED_PAID', 'CLOSED_WRITTEN_OFF')
    tasks_data = []
    seen_recovery_groups = set()
    dirty = False
    for task in due_tasks:
        # Recovery reminders need two guards:
        #  1) Suppress muted / on-hold / closed invoices — muting or holding must
        #     stop the popup, not just the dashboard timer.
        #  2) Collapse duplicates — one customer+salesman group must show a single
        #     popup (it already lists every invoice in that group). Stale/repeat
        #     reminder rows for the same group are retired so they stop flooding
        #     the alarm (this is what caused the "52 reminders" pileup).
        if task.recovery_task_id:
            rt = task.recovery_task
            if not rt or rt.is_muted or rt.is_on_hold or rt.recovery_status in CLOSED_RECOVERY:
                task.is_notification_shown = True
                if not rt or rt.recovery_status in CLOSED_RECOVERY:
                    task.status = 'Cancelled'
                dirty = True
                continue
            inv = rt.invoice if rt else None
            if not inv or inv.status in ('paid', 'cancelled') or inv.is_draft or inv.is_rejected:
                task.is_notification_shown = True
                task.status = 'Cancelled'
                dirty = True
                continue
            gkey = (('grp', inv.customer_id, rt.salesman_id)
                    if rt and inv and inv.customer_id is not None
                    else ('rt', task.recovery_task_id))
            if gkey in seen_recovery_groups:
                task.is_notification_shown = True   # retire the duplicate
                dirty = True
                continue
            seen_recovery_groups.add(gkey)

        if task.linked_invoice_id:
            linv = task.linked_invoice
            if not linv or linv.status in ('paid', 'cancelled') or linv.is_draft or linv.is_rejected:
                task.is_notification_shown = True
                task.status = 'Cancelled'
                dirty = True
                continue

        # Trigger Email Notification if not already sent
        if not task.is_email_sent:
            success, msg = send_task_email(task)
            if success:
                task.is_email_sent = True
                db.session.commit()
            else:
                print(f"Email failed for task {task.id}: {msg}")

        entry = {
            'id': task.id,
            'title': task.title,
            'description': task.description or '',
            'priority': task.priority.name if hasattr(task.priority, 'name') else str(task.priority),
            'is_recovery': task.recovery_task_id is not None,
        }
        # Recovery reminders carry extra context so the popup can offer
        # "promise date + amount" capture and a paid/complete action. One
        # popup Task can represent several of the customer's open invoices
        # (consolidated by app.services.recovery_grouping), so list them all.
        if task.recovery_task_id:
            rtask = task.recovery_task
            inv = rtask.invoice if rtask else None

            invoices = []
            if inv and inv.customer_id:
                from app.services.recovery_grouping import open_tasks_for_group
                group_tasks = open_tasks_for_group(inv.customer_id, rtask.salesman_id)
                # Only list invoices that are still actively being chased — a
                # muted / on-hold / closed invoice must not appear in the popup.
                invoices = [
                    {'invoice_number': t.invoice.invoice_number, 'balance': t.invoice.balance_due}
                    for t in group_tasks
                    if t.invoice and not t.is_muted and not t.is_on_hold
                    and t.recovery_status not in CLOSED_RECOVERY
                ]
            if not invoices and inv:
                invoices = [{'invoice_number': inv.invoice_number, 'balance': inv.balance_due}]

            entry.update({
                'recovery_task_id': task.recovery_task_id,
                'invoice_number': inv.invoice_number if inv else '',
                'customer_name': (inv.customer.name if inv and inv.customer else ''),
                'invoices': invoices,
                'balance': sum(i['balance'] for i in invoices),
            })
        tasks_data.append(entry)

    if dirty:
        db.session.commit()
    return jsonify(tasks_data)

@bp.route('/tasks/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def task_settings():
    settings = TaskSettings.query.first()
    if not settings:
        settings = TaskSettings()
        db.session.add(settings)
        db.session.commit()
        
    form = TaskSettingsForm(obj=settings)
    
    if form.validate_on_submit():
        form.populate_obj(settings)
        db.session.commit()
        flash('Task settings updated successfully.', 'success')
        return redirect(url_for('users.task_settings'))
        
    return render_template('tasks/settings.html', form=form, settings=settings)

@bp.route('/tasks/complete/<int:id>', methods=['POST'])
@login_required
def complete_task_ajax(id):
    task = Task.query.get_or_404(id)
    if current_user.role != 'admin' and task.assigned_to_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    task.status = 'Completed'

    # Bulk recovery reminders (sent to several users at once) share a
    # reminder_batch_id: completing one clears it for every assigned user.
    # Siblings are pre-flagged so only the actor's own row gets announced in
    # the admin "task complete" broadcast (avoids one message per assignee).
    if task.reminder_batch_id:
        siblings = Task.query.filter(
            Task.reminder_batch_id == task.reminder_batch_id,
            Task.id != task.id
        ).all()
        for sib in siblings:
            sib.status = 'Completed'
            sib.is_notification_shown = True
            sib.is_completion_broadcast_shown = True

    db.session.commit()

    log_activity('Tasks', f'Completed Task: {task.title}', 'Update via Alarm Popup')
    return jsonify({'success': True, 'message': 'Task marked as completed'})

@bp.route('/tasks/settings/test', methods=['POST'])
@login_required
@admin_required
def test_task_email():
    from app.services.mail_service import send_task_email
    from app.models import Task
    
    # Create a dummy task for testing
    dummy_task = Task(
        title="Test Task Notification", 
        description="This is a test email from your ERP system.", 
        priority="Medium", 
        reminder_at=datetime.now(),
        assigned_to=current_user
    )
    
    success, msg = send_task_email(dummy_task)
    if success:
        return jsonify({'success': True, 'message': 'Test email sent successfully!'})
    else:
        return jsonify({'success': False, 'message': f'Failed to send test email: {msg}'})

@bp.route('/tasks/acknowledge/<int:id>', methods=['POST'])
@login_required
def acknowledge_task(id):
    task = Task.query.get_or_404(id)
    if current_user.role != 'admin' and task.assigned_to_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
    task.is_notification_shown = True
    db.session.commit()
    return jsonify({'success': True, 'message': 'Reminder acknowledged'})

# ─── Task Group Management (AJAX) ───────────────────────────────────────────

@bp.route('/tasks/groups/list', methods=['GET'])
@login_required
@admin_required
def list_task_groups():
    """Return all task groups as JSON."""
    groups = TaskGroup.query.order_by(TaskGroup.name).all()
    return jsonify([{'id': g.id, 'name': g.name} for g in groups])

@bp.route('/tasks/groups/add', methods=['POST'])
@login_required
@admin_required
def add_task_group():
    """Add a new task group via AJAX POST {name: str}."""
    name = (request.json or {}).get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Group name is required.'}), 400
    if TaskGroup.query.filter_by(name=name).first():
        return jsonify({'success': False, 'message': f'Group "{name}" already exists.'}), 409
    group = TaskGroup(name=name)
    db.session.add(group)
    db.session.commit()
    log_activity('Tasks', f'Created Task Group: {name}', '')
    return jsonify({'success': True, 'id': group.id, 'name': group.name})

@bp.route('/tasks/groups/delete/<int:group_id>', methods=['POST'])
@login_required
@admin_required
def delete_task_group(group_id):
    """Delete a task group. Clears task_group_name on linked tasks."""
    group = TaskGroup.query.get_or_404(group_id)
    group_name = group.name
    # Clear the group name from any tasks that use it
    Task.query.filter_by(task_group_name=group_name).update({'task_group_name': None})
    db.session.delete(group)
    db.session.commit()
    log_activity('Tasks', f'Deleted Task Group: {group_name}', '')
    return jsonify({'success': True, 'message': f'Group "{group_name}" deleted.'})
