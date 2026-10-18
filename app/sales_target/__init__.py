"""Sales Target module - set sales targets for salesmen, teams or the whole
company and track them against actual invoiced sales.

Self-contained, like the Spreadsheet module: its own blueprint
(/sales-target), tables (sales_targets, sales_target_members,
sales_target_products, sales_target_plans, sales_target_plan_parts), templates
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
        try:
            upgrade_plan_tables(db.engine)
        except Exception as e:
            app.logger.error('Sales Target module: could not upgrade yearly plan tables: %s', e)

    from app.sales_target import routes  # noqa: F401  (registers views on bp)
    app.register_blueprint(bp)


def upgrade_plan_tables(engine):
    """One-time upgrade of the yearly-plan tables from the first version
    (quarters only: column ``quarter`` CHECK 1-4) to month or quarter plans
    of any length (``period_no`` 1-12, plans.period_months, plans.period_count).
    Existing plans are kept as full-year quarterly plans. Only these two module tables are touched; it does
    nothing once upgraded. SQLite can't change a CHECK in place, so the
    parts table is rebuilt (create new, copy, drop, rename) in one
    transaction."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    if 'sales_target_plan_parts' not in insp.get_table_names():
        return
    plan_cols = {c['name'] for c in insp.get_columns('sales_target_plans')}
    part_cols = {c['name'] for c in insp.get_columns('sales_target_plan_parts')}
    if {'period_months', 'period_count'} <= plan_cols and 'period_no' in part_cols:
        return
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('automatic upgrade supports SQLite only; run the SQL from the module notes')
    with engine.begin() as conn:
        if 'period_months' not in plan_cols:
            # Plans made before this upgrade were all quarterly.
            conn.exec_driver_sql('ALTER TABLE sales_target_plans '
                                 'ADD COLUMN period_months INTEGER NOT NULL DEFAULT 3 '
                                 'CHECK (period_months IN (1, 3))')
        if 'period_count' not in plan_cols:
            # NULL = full year, which is what every earlier plan was.
            conn.exec_driver_sql('ALTER TABLE sales_target_plans ADD COLUMN period_count INTEGER '
                                 'CHECK (period_count IS NULL OR period_count BETWEEN 1 AND 12)')
        if 'period_no' not in part_cols:
            conn.exec_driver_sql("""
                CREATE TABLE sales_target_plan_parts_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    plan_id INTEGER NOT NULL REFERENCES sales_target_plans (id) ON DELETE CASCADE,
                    target_id INTEGER NOT NULL REFERENCES sales_targets (id) ON DELETE CASCADE,
                    row_no INTEGER NOT NULL,
                    period_no INTEGER NOT NULL,
                    CONSTRAINT uq_sales_target_plan_part_target UNIQUE (target_id),
                    CONSTRAINT uq_sales_target_plan_part_slot UNIQUE (plan_id, row_no, period_no),
                    CONSTRAINT ck_sales_target_plan_parts_period CHECK (period_no BETWEEN 1 AND 12)
                )""")
            conn.exec_driver_sql('INSERT INTO sales_target_plan_parts_new (id, plan_id, target_id, row_no, period_no) '
                                 'SELECT id, plan_id, target_id, row_no, quarter FROM sales_target_plan_parts')
            conn.exec_driver_sql('DROP TABLE sales_target_plan_parts')
            conn.exec_driver_sql('ALTER TABLE sales_target_plan_parts_new RENAME TO sales_target_plan_parts')
            conn.exec_driver_sql('CREATE INDEX IF NOT EXISTS ix_sales_target_plan_parts_plan '
                                 'ON sales_target_plan_parts (plan_id)')
