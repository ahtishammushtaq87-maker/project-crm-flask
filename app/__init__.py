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
    
    # Ensure error handlers work even if debug is True (show friendly errors, not debugger)
    app.config['PROPAGATE_EXCEPTIONS'] = False
    app.config['TRAP_HTTP_EXCEPTIONS'] = False
    
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
            ProductSample, ProductReverseEngineering, ProductDrawing, ProductToolingTrial,
            ProductPrototypeBatch, ProductDevelopmentExpense, ProductBOMVersion,
            ProductRelease, ProductRevisionHistory, SharedCostAllocation, ProductAttachment,
            PurchaseReturn, PurchaseReturnItem, Unit, ActivityLog,
            ToolReceiving, ToolReceivingItem, ToolDelivering, ToolDeliveringItem, ToolSettings,
            ProductWarehouseStock, Media,
            RecoveryTask, RecoveryLog, RecoveryComment, Salesman,
            JournalAccount, JournalEntry, JournalLine, FixedExpense,
            Quotation, QuotationItem, DatabaseBackup, PackingSlip, PackingSlipSettings
        )
        from app.filter_models import SavedFilter
        
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
            'product_samples': ProductSample,
            'product_reverse_engineering': ProductReverseEngineering,
            'product_drawings': ProductDrawing,
            'product_tooling_trials': ProductToolingTrial,
            'product_prototypes': ProductPrototypeBatch,
            'product_development_expenses': ProductDevelopmentExpense,
            'product_bom_versions': ProductBOMVersion,
            'product_release': ProductRelease,
            'product_revision_history': ProductRevisionHistory,
            'shared_cost_allocations': SharedCostAllocation,
            'product_attachments': ProductAttachment,
            'purchase_returns': PurchaseReturn,
            'purchase_return_items': PurchaseReturnItem,
            'saved_filters': SavedFilter,
            'units': Unit,
            'activity_logs': ActivityLog,
            'tool_receiving': ToolReceiving,
            'tool_receiving_items': ToolReceivingItem,
            'tool_delivering': ToolDelivering,
            'tool_delivering_items': ToolDeliveringItem,
            'tool_settings': ToolSettings,
            'product_warehouse_stock': ProductWarehouseStock,
            'media': Media,
            'recovery_tasks': RecoveryTask,
            'recovery_logs': RecoveryLog,
            'recovery_comments': RecoveryComment,
            'salesmen': Salesman,
            'journal_accounts': JournalAccount,
            'journal_entries': JournalEntry,
            'journal_lines': JournalLine,
            'fixed_expenses': FixedExpense,
            'quotations': Quotation,
            'quotation_items': QuotationItem,
            'database_backups': DatabaseBackup,
            'packing_slips': PackingSlip,
            'packing_slip_settings': PackingSlipSettings,
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
    from app.routes.quotation import bp as quotation_bp
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
    from app.routes.filters import bp as filters_bp
    from app.routes.api import bp as api_bp
    from app.routes.activity_log import bp as activity_log_bp
    from app.routes.tools import bp as tools_bp
    from app.routes.media import bp as media_bp
    from app.routes.recovery import bp as recovery_bp
    from app.routes.journal import bp as journal_bp
    from app.routes.backup import bp as backup_bp

    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(accounting_bp, url_prefix='/accounting')
    app.register_blueprint(sales_bp, url_prefix='/sales')
    app.register_blueprint(quotation_bp, url_prefix='/quotation')
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
    app.register_blueprint(filters_bp, url_prefix='/api/filters')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(activity_log_bp, url_prefix='/activity-log')
    app.register_blueprint(tools_bp, url_prefix='/tools')
    app.register_blueprint(media_bp, url_prefix='/media')
    app.register_blueprint(recovery_bp, url_prefix='/recovery')
    app.register_blueprint(journal_bp, url_prefix='/journal')
    app.register_blueprint(backup_bp, url_prefix='/backup')
    
    @app.context_processor
    def inject_company():
         from app.models import Company
         from flask import url_for
         company = Company.query.first()
         logo_url = None
         sig_url = None
         if company:
             if company.logo_path:
                 path = company.logo_path.replace('\\', '/')
                 if 'static/' in path:
                     logo_url = url_for('static', filename=path.split('static/')[-1])
                 else:
                     logo_url = url_for('static', filename=path)
             if company.signature_path:
                 path = company.signature_path.replace('\\', '/')
                 if 'static/' in path:
                     sig_url = url_for('static', filename=path.split('static/')[-1])
                 else:
                     sig_url = url_for('static', filename=path)
         return dict(company=company, company_logo_url=logo_url, company_signature_url=sig_url)
     
     # Global error handlers
    from flask import render_template, request, flash, redirect, url_for, jsonify
    from sqlalchemy.exc import IntegrityError
    
    def safe_render_error(**kwargs):
        """Safely render error template, falling back to plain HTML if needed."""
        try:
            return render_template('error.html', **kwargs)
        except Exception as e:
            app.logger.error(f'Error rendering error page: {e}')
            code = kwargs.get('error_code', 500)
            title = kwargs.get('error_title', 'Error')
            message = kwargs.get('error_message', 'An error occurred.')
            return f"<h1>{code} - {title}</h1><p>{message}</p>", code
    
    def get_user_friendly_message(error):
        """Convert technical errors into one-line simple, understandable messages."""
        error_str = str(error).lower()
        
        # Database integrity errors
        if 'not null constraint' in error_str or 'integrityerror' in error_str:
            if 'sale_id' in error_str:
                return 'Cannot process: Sale ID is required but missing.'
            elif 'product_id' in error_str:
                return 'Cannot process: Product is required. Please select a product.'
            elif 'vendor_id' in error_str or 'customer_id' in error_str:
                return 'Cannot process: Vendor/Customer is required.'
            elif 'bill_id' in error_str:
                return 'Cannot process: Bill reference is missing.'
            else:
                return 'Required field missing or duplicate entry exists. Please check your data.'
        
        # Foreign key constraints
        if 'foreign key constraint' in error_str:
            return 'Cannot save: Referenced record does not exist.'
        
        # Unique constraint violations
        if 'unique constraint' in error_str or 'duplicate' in error_str:
            return 'Duplicate entry: This record already exists.'
        
        # Database errors
        if 'database is locked' in error_str:
            return 'Database busy. Try again in a moment.'
        if 'no such table' in error_str:
            return 'Database setup incomplete. Contact administrator.'
        
        # Default fallback
        return 'An unexpected error occurred. Please try again.'
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'500 Internal Server Error: {request.url} - {error}', exc_info=True)
        user_message = get_user_friendly_message(error)
        
        # AJAX requests get JSON
        if request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(error=user_message), 500
        
        # Regular requests: flash and redirect back
        try:
            flash(user_message, 'danger')
            return redirect(request.referrer or url_for('dashboard.index'))
        except Exception:
            return safe_render_error(
                error_code=500,
                error_title='Server Error',
                error_message=user_message
            ), 500
    
    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.error(f'404 Error: {request.url} - {error}')
        user_message = 'The page you are looking for does not exist.'
        try:
            flash(user_message, 'danger')
            return redirect(request.referrer or url_for('dashboard.index'))
        except Exception:
            return safe_render_error(
                error_code=404,
                error_title='Page Not Found',
                error_message=user_message
            ), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        app.logger.error(f'403 Forbidden: {request.url} - {error}')
        user_message = 'You do not have permission to access this page.'
        try:
            flash(user_message, 'danger')
            return redirect(request.referrer or url_for('dashboard.index'))
        except Exception:
            return safe_render_error(
                error_code=403,
                error_title='Access Denied',
                error_message=user_message
            ), 403
    
    @app.errorhandler(400)
    def bad_request_error(error):
        app.logger.error(f'400 Bad Request: {request.url} - {error}')
        user_message = 'The request could not be understood. Please check your input.'
        try:
            flash(user_message, 'danger')
            return redirect(request.referrer or url_for('dashboard.index'))
        except Exception:
            return safe_render_error(
                error_code=400,
                error_title='Bad Request',
                error_message=user_message
            ), 400
    
    # Catch IntegrityError specifically
    @app.errorhandler(IntegrityError)
    def handle_integrity_error(error):
        app.logger.error(f'IntegrityError: {request.url} - {error}', exc_info=True)
        user_message = get_user_friendly_message(error)
        
        # Rollback to prevent session issues
        try:
            db.session.rollback()
        except:
            pass
        
        if request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(error=user_message), 400
        
        flash(user_message, 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))
    
    # Register custom filters
    from app.utils import format_qty
    app.jinja_env.filters['format_qty'] = format_qty

    # Global helper: render a clickable item-SKU that opens the Item History popup
    from app.utils import sku_link
    app.jinja_env.globals['sku_link'] = sku_link
    import json
    app.jinja_env.filters['from_json'] = json.loads

    # Register approval service as Jinja global for templates
    from app.services.approval_service import ApprovalService
    app.jinja_env.globals['approval_service'] = ApprovalService

    @app.context_processor
    def inject_pending_approvals():
        from flask_login import current_user
        if not current_user.is_authenticated or current_user.role != 'admin':
            return dict(total_pending_approvals=0, pending_approval_details=[])
        try:
            details = []
            total = 0
            module_labels = {
                'sale': 'Invoices', 'payment': 'Payments', 'advance': 'Advances',
                'expense': 'Expenses', 'sale_return': 'Sale Returns',
                'purchase_return': 'Purchase Returns', 'purchase_bill': 'Purchase Bills',
                'purchase_order': 'Purchase Orders', 'bill_payment': 'Bill Payments',
                'product': 'Products', 'tool_receiving': 'Receiving', 'tool_delivering': 'Delivering',
                'bom': 'BOMs', 'manufacturing_order': 'Manufacturing Orders',
                'vendor_advance': 'Vendor Advances',
            }
            for module in module_labels:
                count = ApprovalService.get_pending_count(module)
                if count > 0:
                    details.append({'module': module, 'label': module_labels[module], 'count': count})
                    total += count
            return dict(total_pending_approvals=total, pending_approval_details=details)
        except Exception:
            return dict(total_pending_approvals=0, pending_approval_details=[])

    @app.context_processor
    def inject_overdue_alerts():
        """Top-of-page overdue-invoice notification banner, shown only on Sales
        module pages (see app/templates/base.html). Visible to every user;
        only an admin can dismiss (Sale.overdue_alert_dismissed)."""
        from flask_login import current_user
        if not current_user.is_authenticated or request.blueprint != 'sales':
            return dict(overdue_alert_invoices=[])
        try:
            from app.models import Sale
            candidates = Sale.query.filter(
                Sale.is_approved == True,
                Sale.is_rejected == False,
                Sale.is_draft == False,
                Sale.status != 'paid',
                Sale.due_date.isnot(None),
                Sale.overdue_alert_dismissed == False
            ).all()
            overdue_alert_invoices = [s for s in candidates if s.show_overdue_alert]
            overdue_alert_invoices.sort(key=lambda s: s.days_overdue, reverse=True)
            return dict(overdue_alert_invoices=overdue_alert_invoices)
        except Exception:
            return dict(overdue_alert_invoices=[])

    @app.context_processor
    def inject_recovery_escalation_alerts():
        """Top-of-page notification banner on Recovery module pages, listing
        escalated/critical recovery tasks that are still open — including
        ones sent here from the Sales overdue banner (via admin "Done" or
        the automatic 2-day escalation in recovery_automation.py)."""
        from flask_login import current_user
        if not current_user.is_authenticated or request.blueprint != 'recovery':
            return dict(recovery_escalation_alerts=[])
        try:
            from app.models import RecoveryTask
            tasks = RecoveryTask.query.filter(
                RecoveryTask.is_escalated == True,
                RecoveryTask.recovery_status.notin_(['CLOSED_PAID', 'CLOSED_WRITTEN_OFF'])
            ).order_by(RecoveryTask.escalated_at.desc()).all()
            return dict(recovery_escalation_alerts=tasks)
        except Exception:
            return dict(recovery_escalation_alerts=[])

    from app.scheduler import start_recovery_scheduler, start_backup_scheduler
    start_recovery_scheduler(app)
    start_backup_scheduler(app)

    return app