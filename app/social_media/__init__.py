"""Social Media module - publishing, scheduling, analytics and Meta ads for
Facebook Pages, Instagram professional accounts and LinkedIn, through the
official Meta Graph / Marketing APIs and LinkedIn REST APIs.

Self-contained, like the WhatsApp and Spreadsheet modules: its own
blueprint, tables (social_*), templates (templates/social_media/) and static
files (static/social_media/). Hooks into the rest of the CRM: init_app() in
the app factory and one sidebar group. Existing tables are only read (users).

Blueprint ``social_media`` at /social-media/... Every page is login- and
permission-checked except ``public_media`` (signed, expiring media URLs that
Instagram fetches when publishing).
"""
import os

from flask import Blueprint, abort, request

bp = Blueprint('social_media', __name__, url_prefix='/social-media')

MEDIA_DIR_NAME = 'social_media_media'
_CSRF_EXEMPT = {'social_media.public_media'}


@bp.before_request
def _check_csrf():
    # The CRM has no global CSRFProtect, so this blueprint checks its own
    # POSTs (form field or X-CSRFToken header).
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.endpoint not in _CSRF_EXEMPT:
        from flask_wtf.csrf import CSRFError, validate_csrf
        from wtforms.validators import ValidationError
        token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
        try:
            validate_csrf(token)
        except (ValidationError, CSRFError):
            abort(400, description='Your session expired. Reload the page and try again.')


def _wants_json():
    return request.path.startswith('/social-media/api/') or request.is_json


@bp.errorhandler(400)
@bp.errorhandler(401)
@bp.errorhandler(403)
@bp.errorhandler(404)
@bp.errorhandler(413)
def _http_error(error):
    """JSON endpoints get JSON and the real status code; pages flash the
    message and go back, like the rest of the CRM."""
    from flask import flash, jsonify, redirect, url_for
    messages = {400: 'The request was rejected. Reload the page and try again.',
                401: 'Please sign in again.', 403: 'You do not have permission to do this.',
                404: 'Not found.', 413: 'The upload is too large.'}
    code = getattr(error, 'code', 400) or 400
    desc = getattr(error, 'description', None)
    text = desc if code == 400 and desc and 'session expired' in desc else messages.get(code, 'Request failed.')
    if _wants_json():
        return jsonify({'ok': False, 'error': text, 'code': code}), code
    if request.endpoint == 'social_media.public_media':
        return text, code
    flash(text, 'danger')
    return redirect(request.referrer or url_for('social_media.overview')), 302


def media_root(app=None):
    """Private media folder (inside instance/, never under static/)."""
    from flask import current_app
    app = app or current_app
    path = os.path.join(app.instance_path, MEDIA_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def init_app(app):
    """Create the module's tables and indexes if missing. Idempotent: it never
    alters, drops or rewrites anything, so it is safe on a live database."""
    from app import db
    from app.social_media.models import ALL_MODELS

    with app.app_context():
        try:
            for model in ALL_MODELS:
                model.__table__.create(db.engine, checkfirst=True)
                for index in model.__table__.indexes:
                    index.create(db.engine, checkfirst=True)
            # Columns added after the first release (additive only).
            from sqlalchemy import inspect, text
            cols = {c['name'] for c in inspect(db.engine).get_columns('social_posts')}
            if 'preview_image_url' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE social_posts ADD COLUMN preview_image_url VARCHAR(2000)'))
        except Exception as e:  # never block the CRM from starting
            app.logger.error('Social Media module: could not create tables: %s', e)

    from flask_wtf.csrf import generate_csrf
    app.jinja_env.globals['sm_csrf_token'] = generate_csrf

    from app.social_media import permissions
    app.jinja_env.globals['sm_can'] = permissions.can

    from app.social_media import filters
    filters.register(app)

    from app.social_media import routes, oauth_routes, ads_routes  # noqa: F401  (register views)
    app.register_blueprint(bp)

    from app.social_media.services.scheduler import start_scheduler
    start_scheduler(app)
