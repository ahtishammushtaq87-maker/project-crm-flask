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
    
    # Disable Jinja2 template caching to ensure fresh renders (development)
    app.jinja_env.cache = None
    
    # Disable Jinja2 template caching to ensure fresh renders (development)
    app.jinja_env.cache = None
    
    db.init_app(app)
    
    # Auto-migrate missing columns
    with app.app_context():
        from sqlalchemy import inspect, text
        try:
            inspector = inspect(db.engine)
            existing_columns = [c['name'] for c in inspector.get_columns('users')]
            required_columns = ['can_view_sales', 'can_view_purchases', 'can_view_inventory',
                'can_view_expenses', 'can_view_returns', 'can_view_vendors',
                'can_view_customers', 'can_view_reports', 'can_view_settings',
                'can_view_manufacturing', 'can_view_production', 'can_view_warehouse',
                'can_view_attendance', 'can_view_salary', 'can_view_targets',
                'can_view_dashboard', 'can_view_accounting']
            with db.engine.connect() as conn:
                for col in required_columns:
                    if col not in existing_columns:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} BOOLEAN DEFAULT true"))
                        conn.commit()
                        print(f"Added column: {col}")
        except Exception as e:
            print(f"Migration check: {e}")
        
        # Migrate expenses table for is_bom_overhead column
        try:
            inspector = inspect(db.engine)
            expense_columns = [c['name'] for c in inspector.get_columns('expenses')]
            if 'is_bom_overhead' not in expense_columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN is_bom_overhead BOOLEAN DEFAULT false"))
                    conn.commit()
                    print("Added column: is_bom_overhead to expenses")
        except Exception as e:
            print(f"Expenses migration check: {e}")
        
        # Migrate products table for is_manufactured column
        try:
            inspector = inspect(db.engine)
            product_columns = [c['name'] for c in inspector.get_columns('products')]
            if 'is_manufactured' not in product_columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE products ADD COLUMN is_manufactured BOOLEAN DEFAULT false"))
                    conn.commit()
                    print("Added column: is_manufactured to products")
        except Exception as e:
            print(f"Products migration check: {e}")
        
        # Migrate expenses table for product_id and bom_id columns
        try:
            inspector = inspect(db.engine)
            expense_columns = [c['name'] for c in inspector.get_columns('expenses')]
            with db.engine.connect() as conn:
                if 'product_id' not in expense_columns:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN product_id INTEGER"))
                    conn.commit()
                    print("Added column: product_id to expenses")
                if 'bom_id' not in expense_columns:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN bom_id INTEGER"))
                    conn.commit()
                    print("Added column: bom_id to expenses")
                if 'is_monthly_divided' not in expense_columns:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN is_monthly_divided BOOLEAN DEFAULT false"))
                    conn.commit()
                    print("Added column: is_monthly_divided to expenses")
                if 'monthly_start_date' not in expense_columns:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN monthly_start_date DATE"))
                    conn.commit()
                    print("Added column: monthly_start_date to expenses")
                if 'monthly_end_date' not in expense_columns:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN monthly_end_date DATE"))
                    conn.commit()
                    print("Added column: monthly_end_date to expenses")
        except Exception as e:
            print(f"Expenses product/bom migration check: {e}")
            
        # Migrate for monthly_targets table
        try:
            inspector = inspect(db.engine)
            if 'monthly_targets' not in inspector.get_table_names():
                from app.models import MonthlyTarget
                MonthlyTarget.__table__.create(db.engine)
                print("Created monthly_targets table")
        except Exception as e:
            print(f"Monthly targets table check: {e}")
        
        # Migrate sale_returns table for returned_to_inventory column
        try:
            inspector = inspect(db.engine)
            returns_columns = [c['name'] for c in inspector.get_columns('sale_returns')]
            if 'returned_to_inventory' not in returns_columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE sale_returns ADD COLUMN returned_to_inventory BOOLEAN DEFAULT false"))
                    conn.commit()
                    print("Added column: returned_to_inventory to sale_returns")
        except Exception as e:
            print(f"Sale_returns migration check: {e}")
        
        # Create warehouses table if not exists
        try:
            inspector = inspect(db.engine)
            if 'warehouses' not in inspector.get_table_names():
                from app.models import Warehouse
                Warehouse.__table__.create(db.engine)
                print("Created warehouses table")
        except Exception as e:
            print(f"Warehouses table check: {e}")
        
        # Migrate products table for warehouse_id column
        try:
            inspector = inspect(db.engine)
            product_columns = [c['name'] for c in inspector.get_columns('products')]
            if 'warehouse_id' not in product_columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE products ADD COLUMN warehouse_id INTEGER"))
                    conn.commit()
                    print("Added column: warehouse_id to products")
        except Exception as e:
            print(f"Products warehouse_id migration check: {e}")
        
        # Migrate for production_targets table
        try:
            inspector = inspect(db.engine)
            if 'production_targets' not in inspector.get_table_names():
                from app.models import ProductionTarget
                ProductionTarget.__table__.create(db.engine)
                print("Created production_targets table")
        except Exception as e:
            print(f"Production targets table check: {e}")
        
        # Migrate for production_logs table
        try:
            inspector = inspect(db.engine)
            if 'production_logs' not in inspector.get_table_names():
                from app.models import ProductionLog
                ProductionLog.__table__.create(db.engine)
                print("Created production_logs table")
        except Exception as e:
            print(f"Production logs table check: {e}")
        
        # Migrate for Product Development tables
        try:
            from app.models import PDProject, PDProjectBOM, PDComponent, PDTooling, PDTesting, PDApproval, PDAsset
            inspector = inspect(db.engine)
            tables_to_create = {
                'pd_projects': PDProject,
                'pd_bom': PDProjectBOM,
                'pd_components': PDComponent,
                'pd_tooling': PDTooling,
                'pd_testing': PDTesting,
                'pd_approval': PDApproval,
                'pd_assets': PDAsset
            }
            existing_tables = inspector.get_table_names()
            for table_name, model_class in tables_to_create.items():
                if table_name not in existing_tables:
                    model_class.__table__.create(db.engine)
                    print(f"Created {table_name} table")
        except Exception as e:
            print(f"Product Development tables check: {e}")
        
        # Migrate company table for signature_path column
        try:
            inspector = inspect(db.engine)
            company_columns = [c['name'] for c in inspector.get_columns('company')]
            if 'signature_path' not in company_columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE company ADD COLUMN signature_path VARCHAR(200)"))
                    conn.commit()
                    print("Added column: signature_path to company")
        except Exception as e:
            print(f"Company signature_path migration check: {e}")
    
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
    
    @app.context_processor
    def inject_company():
        from app.models import Company
        from flask import url_for
        company = Company.query.first()
        logo_url = None
        if company and company.logo_path:
            # Normalize path and extract static-relative part correctly
            path = company.logo_path.replace('\\', '/')
            if 'static/' in path:
                # Get everything AFTER static/
                logo_url = url_for('static', filename=path.split('static/')[-1])
            else:
                logo_url = url_for('static', filename=path)
        return dict(company=company, company_logo_url=logo_url)
    
    return app