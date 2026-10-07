"""Spreadsheet module - a Google Sheets-style workbook editor inside the CRM.

Self-contained: its own blueprint (/sheets), models/tables (spreadsheet*),
templates (templates/sheets/) and static files (static/sheets/). The only
hooks into the rest of the CRM are init_app() in the app factory and a
sidebar link.
"""
from flask import Blueprint

bp = Blueprint('sheets', __name__, url_prefix='/sheets')


def init_app(app):
    """Create the module's tables if missing (never alters or drops
    anything) and register the blueprint."""
    from app import db
    from app.sheets.models import ALL_MODELS

    with app.app_context():
        try:
            for model in ALL_MODELS:
                model.__table__.create(db.engine, checkfirst=True)
        except Exception as e:  # never block the CRM from starting
            app.logger.error('Spreadsheet module: could not create tables: %s', e)

    from app.sheets import routes, api  # noqa: F401  (registers views on bp)
    app.register_blueprint(bp)
