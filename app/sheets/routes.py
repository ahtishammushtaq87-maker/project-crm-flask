"""HTML pages of the Spreadsheet module. Data is loaded by the pages from
the JSON API (api.py); these routes only check access and render shells."""
from flask import render_template, abort, flash, redirect, url_for
from flask_login import login_required, current_user
from flask_wtf.csrf import generate_csrf

from app import db
from app.sheets import bp, permissions as P
from app.sheets.models import Spreadsheet


@bp.route('/')
@login_required
def index():
    return render_template('sheets/index.html', csrf_token_value=generate_csrf(),
                           is_admin=P.is_crm_admin(current_user))


@bp.route('/<int:book_id>')
@login_required
def editor(book_id):
    ss = db.session.get(Spreadsheet, book_id)
    role = P.role_for(current_user, ss)
    if not ss or not P.can_view(role) or (ss.is_deleted and not P.is_crm_admin(current_user)):
        # Same answer whether it doesn't exist or isn't shared with you.
        flash('Spreadsheet not found, or it has not been shared with you.', 'warning')
        return redirect(url_for('sheets.index'))
    return render_template('sheets/editor.html', book=ss, role=role, csrf_token_value=generate_csrf())


@bp.route('/admin')
@login_required
def admin():
    if not P.is_crm_admin(current_user):
        abort(403)
    return render_template('sheets/admin.html', csrf_token_value=generate_csrf())
