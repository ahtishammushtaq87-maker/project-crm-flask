from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import ActivityLog, User, db
from app.utils import permission_required
from datetime import datetime, timedelta
from sqlalchemy import or_

bp = Blueprint('activity_log', __name__)

@bp.route('/')
@login_required
@permission_required('activity_logs', action='view')
def index():

    # Filters
    user_id = request.args.get('user_id')
    module = request.args.get('module')
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')
    search = request.args.get('search', '')

    query = ActivityLog.query

    if user_id:
        query = query.filter_by(user_id=user_id)
    
    if module:
        query = query.filter_by(module=module)

    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
            query = query.filter(ActivityLog.timestamp >= date_from)
        except ValueError:
            pass

    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(ActivityLog.timestamp <= date_to)
        except ValueError:
            pass

    if search:
        query = query.filter(or_(
            ActivityLog.action.ilike(f'%{search}%'),
            ActivityLog.details.ilike(f'%{search}%'),
            ActivityLog.module.ilike(f'%{search}%')
        ))

    logs = query.order_by(ActivityLog.timestamp.desc()).all()
    users = User.query.filter_by(is_active=True).all()
    
    # Get unique modules for the filter dropdown
    modules = db.session.query(ActivityLog.module).distinct().all()
    modules = [m[0] for m in modules if m[0]]

    return render_template('activity_log/index.html',
                           logs=logs,
                           users=users,
                           modules=modules,
                           selected_user_id=int(user_id) if user_id else None,
                           selected_module=module,
                           date_from=date_from_str,
                           date_to=date_to_str,
                           search=search)
