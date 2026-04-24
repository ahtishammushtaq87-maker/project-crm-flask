from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    config_class.init_app(app)
    
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
    
    # Disable Jinja2 template caching to ensure fresh renders (development)
    app.jinja_env.cache = None
    
    db.init_app(app)
    
    # Auto-migrate missing columns and tables
    with app.app_context():
        from sqlalchemy import inspect, text
        from app.models import (
            User, Vendor, Customer, Warehouse, Product, ProductCategory, Sale, SaleItem,
            PurchaseBill, PurchaseItem, Transaction, Account, TaxRate,
            Currency, Payment, RecurringExpense, ExpenseCategory, Expense,
            StockMovement, Company, InvoiceSettings, PurchaseSettings, ExpenseSettings,
            SaleReturn, SaleReturnItem, Task, BOM, BOMItem, Staff,
            Attendance, SalaryAdvance, SalaryPayment, ManufacturingOrder,
            ManufacturingOrderItem, MonthlyTarget, VendorAdvance, CustomerAdvance,
            PurchaseOrder, PurchaseOrderItem, CostPriceHistory, BOMVersion,
            BOMVersionItem, ProductionTarget, ProductionLog, PDProject,
            PDProjectBOM, PDComponent, PDTooling, PDTesting, PDApproval, PDAsset,
            PurchaseReturn, PurchaseReturnItem
        )
        
        # Map model classes to table names and their columns
        model_columns = {
            'users': User,
            'vendors': Vendor,
            'customers': Customer,
            'warehouses': Warehouse,
            'products': Product,
            'product_categories': ProductCategory,
            'sales': Sale,
            'sale_items': SaleItem,
            'purchase_bills': PurchaseBill,
            'purchase_items': PurchaseItem,
            'transactions': Transaction,
            'accounts': Account,
            'tax_rates': TaxRate,
            'currencies': Currency,
            'payments': Payment,
            'recurring_expenses': RecurringExpense,
            'expense_categories': ExpenseCategory,
            'expenses': Expense,
            'stock_movements': StockMovement,
            'company': Company,
            'invoice_settings': InvoiceSettings,
            'purchase_settings': PurchaseSettings,
            'expense_settings': ExpenseSettings,
            'sale_returns': SaleReturn,
            'sale_return_items': SaleReturnItem,
            'tasks': Task,
            'boms': BOM,
            'bom_items': BOMItem,
            'staff': Staff,
            'attendance': Attendance,
            'salary_advances': SalaryAdvance,
            'salary_payments': SalaryPayment,
            'manufacturing_orders': ManufacturingOrder,
            'manufacturing_order_items': ManufacturingOrderItem,
            'monthly_targets': MonthlyTarget,
            'vendor_advances': VendorAdvance,
            'customer_advances': CustomerAdvance,
            'purchase_orders': PurchaseOrder,
            'purchase_order_items': PurchaseOrderItem,
            'cost_price_history': CostPriceHistory,
            'bom_versions': BOMVersion,
            'bom_version_items': BOMVersionItem,
            'production_targets': ProductionTarget,
            'production_logs': ProductionLog,
            'pd_projects': PDProject,
            'pd_bom': PDProjectBOM,
            'pd_components': PDComponent,
            'pd_tooling': PDTooling,
            'pd_testing': PDTesting,
            'pd_approval': PDApproval,
            'pd_assets': PDAsset,
            'purchase_returns': PurchaseReturn,
            'purchase_return_items': PurchaseReturnItem
        }
        
        try:
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            for table_name, model_class in model_columns.items():
                # Create table if it doesn't exist
                if table_name not in existing_tables:
                    try:
                        model_class.__table__.create(db.engine)
                        print(f"Created table: {table_name}")
                    except Exception as e:
                        print(f"Error creating table {table_name}: {e}")
                    continue
                
                # Get existing columns
                try:
                    existing_columns = [c['name'] for c in inspector.get_columns(table_name)]
                except Exception as e:
                    print(f"Error getting columns for {table_name}: {e}")
                    continue
                
                # Get columns from model
                model_columns_dict = {c.name: c for c in model_class.__table__.columns}
                
                # Add missing columns
                with db.engine.connect() as conn:
                    for col_name, col_obj in model_columns_dict.items():
                        if col_name not in existing_columns:
                            # Get the base type
                            col_type_str = str(col_obj.type)
                            base_type = col_type_str.split('(')[0].upper()
                            
                            # Map SQLAlchemy types to PostgreSQL types
                            type_mapping = {
                                'INTEGER': 'INTEGER',
                                'FLOAT': 'FLOAT',
                                'REAL': 'REAL',
                                'NUMERIC': 'NUMERIC',
                                'DECIMAL': 'NUMERIC',
                                'VARCHAR': 'VARCHAR',
                                'TEXT': 'TEXT',
                                'BOOLEAN': 'BOOLEAN',
                                'DATE': 'DATE',
                                'DATETIME': 'TIMESTAMP',
                                'TIMESTAMP': 'TIMESTAMP',
                            }
                            
                            pg_type = type_mapping.get(base_type, 'TEXT')
                            
                            # Handle VARCHAR with length
                            if pg_type == 'VARCHAR':
                                if '(' in col_type_str:
                                    # Extract length from type string
                                    length_str = col_type_str.split('(')[1].split(')')[0]
                                    pg_type = f'VARCHAR({length_str})'
                                else:
                                    pg_type = 'VARCHAR(255)'
                            
                            # Handle NUMERIC/DECIMAL with precision
                            if pg_type == 'NUMERIC' and '(' in col_type_str:
                                pg_type = 'NUMERIC(10,2)'
                            
                            # Get default value
                            default = col_obj.default
                            default_str = ''
                            if default and default.arg is not None:
                                if isinstance(default.arg, bool):
                                    default_str = f" DEFAULT {default.arg}"
                                elif isinstance(default.arg, (int, float)):
                                    default_str = f" DEFAULT {default.arg}"
                                elif isinstance(default.arg, str):
                                    default_str = f" DEFAULT '{default.arg}'"
                            
                            try:
                                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {pg_type}{default_str}"))
                                conn.commit()
                                print(f"Added column: {col_name} to {table_name}")
                            except Exception as col_err:
                                print(f"Error adding {col_name} to {table_name}: {col_err}")
        except Exception as e:
            print(f"Auto-migration error: {e}")
    
    # Enable SQLite foreign key constraints
    if app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith('sqlite'):
        with app.app_context():
            from sqlalchemy import event
            @event.listens_for(db.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
            
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Register blueprints
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.accounting import bp as accounting_bp
    from app.routes.sales import bp as sales_bp
    from app.routes.inventory import bp as inventory_bp
    from app.routes.warehouse import bp as warehouse_bp
    from app.routes.purchase import bp as purchase_bp
    from app.routes.reports import bp as reports_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.users import bp as users_bp
    from app.routes.returns import bp as returns_bp
    from app.routes.manufacturing import bp as manufacturing_bp
    from app.routes.salary import bp as salary_bp
    from app.routes.attendance import bp as attendance_bp
    from app.routes.reports_attendance import bp as reports_attendance_bp
    from app.routes.targets import bp as targets_bp
    from app.routes.production import bp as production_bp
    from app.routes.product_development import bp as pd_bp
    from app.routes.categories import bp as categories_bp

    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(accounting_bp, url_prefix='/accounting')
    app.register_blueprint(sales_bp, url_prefix='/sales')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(warehouse_bp, url_prefix='/warehouse')
    app.register_blueprint(purchase_bp, url_prefix='/purchase')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(reports_attendance_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(returns_bp, url_prefix='/returns')
    app.register_blueprint(manufacturing_bp, url_prefix='/manufacturing')
    app.register_blueprint(salary_bp, url_prefix='/salary')
    app.register_blueprint(attendance_bp)
    app.register_blueprint(targets_bp, url_prefix='/targets')
    app.register_blueprint(production_bp, url_prefix='/production')
    app.register_blueprint(pd_bp, url_prefix='/product-development')
    app.register_blueprint(categories_bp, url_prefix='/categories')
    
    @app.context_processor
    def inject_company():
        from app.models import Company
        from flask import url_for
        company = Company.query.first()
        logo_url = None
        if company and company.logo_path:
            path = company.logo_path.replace('\\', '/')
            if 'static/' in path:
                logo_url = url_for('static', filename=path.split('static/')[-1])
            else:
                logo_url = url_for('static', filename=path)
        return dict(company=company, company_logo_url=logo_url)
    
    # Global error handlers
    from flask import render_template, request
    
    def safe_render_error(**kwargs):
        """Safely render error template, falling back to plain HTML if needed."""
        try:
            return render_template('error.html', **kwargs)
        except Exception as e:
            app.logger.error(f'Error rendering error page: {e}')
            # Fallback plain HTML response
            code = kwargs.get('error_code', 500)
            title = kwargs.get('error_title', 'Error')
            message = kwargs.get('error_message', 'An error occurred.')
            return f"<h1>{code} - {title}</h1><p>{message}</p>", code
    
    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.error(f'404 Error: {request.url} - {error}')
        return safe_render_error(
            error_code=404,
            error_title='Page Not Found',
            error_message='The page you are looking for does not exist or has been moved.'
        ), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'500 Internal Server Error: {request.url} - {error}', exc_info=True)
        return safe_render_error(
            error_code=500,
            error_title='Server Error',
            error_message='An unexpected error occurred. Our team has been notified. Please try again later.'
        ), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        app.logger.error(f'403 Forbidden: {request.url} - {error}')
        return safe_render_error(
            error_code=403,
            error_title='Access Denied',
            error_message='You do not have permission to access this page.'
        ), 403
    
    @app.errorhandler(400)
    def bad_request_error(error):
        app.logger.error(f'400 Bad Request: {request.url} - {error}')
        return safe_render_error(
            error_code=400,
            error_title='Bad Request',
            error_message='The request could not be understood. Please check your input and try again.'
        ), 400
    
    return app