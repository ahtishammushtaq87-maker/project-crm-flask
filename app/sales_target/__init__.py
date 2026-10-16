"""Sales Target module - set sales targets for salesmen, teams or the whole
company and track them against actual invoiced sales.

Self-contained, like the Spreadsheet module: its own blueprint
(/sales-target), tables (sales_targets, sales_target_members), templates
(templates/sales_target/) and static files (static/sales_target/). Hooks into
the rest of the CRM: init_app() in the app factory and one sidebar link.
Existing invoice/return/salesman tables are only read, never written.
"""
from flask import Blueprint

bp = Blueprint('sales_target', __name__, url_prefix='/sales-target')


def init_app(app):
    """Create the module's tables and indexes if missing. Idempotent: it never
    alters, drops or rewrites anything, so it is safe on a live database."""
    from app import db
    from app.sales_target.models import ALL_MODELS

    with app.app_context():
        try:
            for model in ALL_MODELS:
                # checkfirst skips anything that already exists. Indexes are
                # checked one by one, so if a startup ever stops between the
                # table and its indexes, the next startup adds what is missing.
                model.__table__.create(db.engine, checkfirst=True)
                for index in model.__table__.indexes:
                    index.create(db.engine, checkfirst=True)
        except Exception as e:  # never block the CRM from starting
            app.logger.error('Sales Target module: could not create tables: %s', e)

    from app.sales_target import routes  # noqa: F401  (registers views on bp)
    app.register_blueprint(bp)
