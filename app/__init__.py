from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    
    # Auto-migrate missing columns
    with app.app_context():
        from sqlalchemy import inspect, text
        try:
            inspector = inspect(db.engine)
            existing_columns = [c['name'] for c in inspector.get_columns('users')]
            required_columns = ['can_view_sales', 'can_view_purchases', 'can_view_inventory',
                'can_view_expenses', 'can_view_returns', 'can_view_vendors',
                'can_view_customers', 'can_view_reports', 'can_view_settings']
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
        except Exception as e:
            print(f"Expenses product/bom migration check: {e}")
    
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
    from app.routes.purchase import bp as purchase_bp
    from app.routes.reports import bp as reports_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.users import bp as users_bp
    from app.routes.returns import bp as returns_bp
    from app.routes.manufacturing import bp as manufacturing_bp
    from app.routes.salary import bp as salary_bp

    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(accounting_bp, url_prefix='/accounting')
    app.register_blueprint(sales_bp, url_prefix='/sales')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(purchase_bp, url_prefix='/purchase')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(returns_bp, url_prefix='/returns')
    app.register_blueprint(manufacturing_bp, url_prefix='/manufacturing')
    app.register_blueprint(salary_bp, url_prefix='/salary')
    
    return app