"""Admin "Login as user": an administrator opens the CRM as another user to
check what that user sees and can do (permission testing), then returns to
their own account with one click.

Self-contained: no new tables. The session remembers who started it:
    session['impersonation'] = {'admin_id': <admin>, 'user_id': <target>}
Hooks into the rest of the CRM: init_app() in the app factory, a button on
User Management (users/index.html) and a banner in base.html.

Safety rules (all enforced on the server):
  * only a real administrator who is not already impersonating can start;
  * not for themselves, other administrators, or inactive users;
  * if the signed-in user stops matching the remembered target (logout,
    fresh sign-in, ...), the impersonation record is dropped, so a leftover
    "Return to admin" can never sign anyone in as the administrator;
  * start and return are written to the Activity Log.
"""
from flask import Blueprint

bp = Blueprint('impersonation', __name__, url_prefix='/users/impersonate')
SESSION_KEY = 'impersonation'


def init_app(app):
    from flask_wtf.csrf import generate_csrf
    from app.impersonation import routes

    app.register_blueprint(bp)
    app.before_request(routes.guard_session)
    app.context_processor(routes.inject_banner)
    # CSRF token for the Login-as / Return buttons (the app has no global
    # CSRFProtect, so templates don't otherwise get csrf_token()).
    app.jinja_env.globals['impersonation_csrf_token'] = generate_csrf

    def can_impersonate_user(target):
        from flask_login import current_user
        return routes.can_impersonate(current_user, target)[0]
    app.jinja_env.globals['can_impersonate_user'] = can_impersonate_user
