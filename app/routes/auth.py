from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.utils import log_activity
from werkzeug.security import check_password_hash
from app import db
from app.models import User
from app.forms import LoginForm

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        from app.system_mail import reset as password_reset
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account is inactive. Please contact admin to activate your account.', 'warning')
            else:
                login_user(user)
                session.pop('must_change_password', None)
                password_reset.revoke_pending(user)
                log_activity('Auth', 'Login', f'User logged into the system')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('dashboard.index'))
        else:
            # A one-time temporary password from "Forgot password?"
            temp_user = None
            if user and user.is_active:
                temp_user = password_reset.login_with_temp_password(form.username.data, form.password.data)
            if temp_user:
                login_user(temp_user)
                session['must_change_password'] = True
                log_activity('Auth', 'Login', 'Signed in with a temporary password')
                flash('You signed in with a temporary password. Please choose a new password now.', 'warning')
                return redirect(url_for('password_reset.change_password'))
            flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    log_activity('Auth', 'Logout', f'User logged out from the system')
    logout_user()
    return redirect(url_for('auth.login'))