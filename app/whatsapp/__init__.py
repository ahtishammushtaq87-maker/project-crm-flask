"""WhatsApp module - shared inbox, contacts, templates, campaigns, automations
and reports on the official Meta WhatsApp Business Platform (Cloud API).

Self-contained, like the Sales Target and Spreadsheet modules: its own
blueprints, tables (whatsapp_*), templates (templates/whatsapp/) and static
files (static/whatsapp/). Hooks into the rest of the CRM: init_app() in the app
factory, one sidebar group, a button on the customer profile and an optional
background job. Existing tables are only read (customers, sales, users) or
written through their normal models (tasks created by automations).

Blueprints:
  * whatsapp          /whatsapp/...           signed-in staff, permission-checked
  * whatsapp_webhook  /webhooks/whatsapp      Meta server-to-server (no login;
                                              protected by X-Hub-Signature-256)
"""
import os

from flask import Blueprint, abort, request

bp = Blueprint('whatsapp', __name__, url_prefix='/whatsapp')
webhook_bp = Blueprint('whatsapp_webhook', __name__)


@bp.before_request
def _check_csrf():
    # The CRM has no global CSRFProtect, so this blueprint checks its own
    # POSTs (form field or X-CSRFToken header). The webhook blueprint is
    # separate and uses the Meta signature instead.
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        from flask_wtf.csrf import CSRFError, validate_csrf
        from wtforms.validators import ValidationError
        token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
        try:
            validate_csrf(token)
        except (ValidationError, CSRFError):
            abort(400, description='Your session expired. Reload the page and try again.')


def _wants_json():
    return request.path.startswith('/whatsapp/api/') or request.is_json


@bp.errorhandler(400)
@bp.errorhandler(401)
@bp.errorhandler(403)
@bp.errorhandler(404)
@bp.errorhandler(413)
def _http_error(error):
    """The inbox API answers with JSON and the real status code (the CRM's
    app-wide handlers redirect, which a fetch() can't use). Pages keep the
    CRM's behaviour: flash the message and go back."""
    from flask import flash, jsonify, redirect, url_for
    messages = {400: 'The request was rejected. Reload the page and try again.',
                401: 'Please sign in again.', 403: 'You do not have permission to do this.',
                404: 'Not found.', 413: 'The file is too large.'}
    code = getattr(error, 'code', 400) or 400
    desc = getattr(error, 'description', None)
    text = desc if code == 400 and desc and 'session expired' in desc else messages.get(code, 'Request failed.')
    if _wants_json():
        return jsonify({'ok': False, 'error': text, 'code': code}), code
    flash(text, 'danger')
    return redirect(request.referrer or url_for('whatsapp.dashboard')), 302

MEDIA_DIR_NAME = 'whatsapp_media'


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
    from app.whatsapp.models import ALL_MODELS

    with app.app_context():
        try:
            for model in ALL_MODELS:
                model.__table__.create(db.engine, checkfirst=True)
                for index in model.__table__.indexes:
                    index.create(db.engine, checkfirst=True)
        except Exception as e:  # never block the CRM from starting
            app.logger.error('WhatsApp module: could not create tables: %s', e)

    from flask_wtf.csrf import generate_csrf
    app.jinja_env.globals['wa_csrf_token'] = generate_csrf

    from app.whatsapp import permissions
    app.jinja_env.globals['wa_can'] = permissions.can

    from app.whatsapp import filters
    filters.register(app)

    from app.whatsapp import routes, api, webhook_routes  # noqa: F401  (register views)
    app.register_blueprint(bp)
    app.register_blueprint(webhook_bp)

    from app.whatsapp.services.jobs import start_scheduler
    start_scheduler(app)
