from app import create_app, db
from sqlalchemy import text

app = create_app()

def update_schema():
    with app.app_context():
        columns = [
            ('can_view_sales', 'BOOLEAN DEFAULT 1'),
            ('can_view_purchases', 'BOOLEAN DEFAULT 1'),
            ('can_view_inventory', 'BOOLEAN DEFAULT 1'),
            ('can_view_expenses', 'BOOLEAN DEFAULT 1'),
            ('can_view_returns', 'BOOLEAN DEFAULT 1'),
            ('can_view_vendors', 'BOOLEAN DEFAULT 1'),
            ('can_view_customers', 'BOOLEAN DEFAULT 1'),
            ('can_view_reports', 'BOOLEAN DEFAULT 1'),
            ('can_view_settings', 'BOOLEAN DEFAULT 1'),
        ]
        
        with db.engine.connect() as conn:
            # Check existing columns
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            existing_columns = [c['name'] for c in inspector.get_columns('users')]
            
            for col_name, col_type in columns:
                if col_name not in existing_columns:
                    print(f"Adding column {col_name} to users table...")
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                else:
                    print(f"Column {col_name} already exists.")
                    
        print("Schema update completed successfully!")

if __name__ == "__main__":
    update_schema()
