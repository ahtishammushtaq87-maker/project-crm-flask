"""System email (SMTP) settings and "Forgot password" by email.

Self-contained like the Spreadsheet and Sales Target modules: its own tables
(mail_settings, password_resets), templates (templates/system_mail/) and two
blueprints:
  * password_reset  /auth/forgot-password (POST from the sign-in page),
                    /auth/change-password (opens after signing in with the
                    temporary password)
  * system_mail     /settings/email   (admins only)
Hooks into the rest of the CRM: init_app() in the app factory, a link on the
login page, one sidebar link, and a temporary-password check in auth.login.
"""
from flask import Blueprint

reset_bp = Blueprint('password_reset', __name__, url_prefix='/auth')
settings_bp = Blueprint('system_mail', __name__, url_prefix='/settings/email')


def init_app(app):
    """Create the module's tables/indexes if missing (never alters or drops
    anything) and register the blueprints."""
    from app import db
    from app.system_mail.models import ALL_MODELS

    with app.app_context():
        try:
            for model in ALL_MODELS:
                model.__table__.create(db.engine, checkfirst=True)
                for index in model.__table__.indexes:
                    index.create(db.engine, checkfirst=True)
        except Exception as e:  # never block the CRM from starting
            app.logger.error('System mail module: could not create tables: %s', e)

    from app.system_mail import routes
    app.register_blueprint(reset_bp)
    app.register_blueprint(settings_bp)
    app.before_request(routes.enforce_password_change)
