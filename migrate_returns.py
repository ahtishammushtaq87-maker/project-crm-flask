from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

def migrate():
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Get actual columns from database
        existing_columns = [c['name'] for c in inspector.get_columns('users')]
        print(f"Existing columns: {existing_columns}")
        
        # Required columns based on model
        required_columns = [
            'can_view_sales', 'can_view_purchases', 'can_view_inventory',
            'can_view_expenses', 'can_view_returns', 'can_view_vendors',
            'can_view_customers', 'can_view_reports', 'can_view_settings'
        ]
        
        with db.engine.connect() as conn:
            for col in required_columns:
                if col not in existing_columns:
                    try:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} BOOLEAN DEFAULT true"))
                        conn.commit()
                        print(f"Added column: {col}")
                    except Exception as e:
                        print(f"Error adding {col}: {e}")
                else:
                    print(f"Column exists: {col}")
        
        inspector = inspect(db.engine)
        existing_returns_columns = [c['name'] for c in inspector.get_columns('sale_returns')]
        print(f"Existing sale_returns columns: {existing_returns_columns}")
        
        returns_required_columns = ['returned_to_inventory']
        
        with db.engine.connect() as conn:
            for col in returns_required_columns:
                if col not in existing_returns_columns:
                    try:
                        conn.execute(text(f"ALTER TABLE sale_returns ADD COLUMN {col} BOOLEAN DEFAULT false"))
                        conn.commit()
                        print(f"Added column: {col}")
                    except Exception as e:
                        print(f"Error adding {col}: {e}")
                else:
                    print(f"Column exists: {col}")
        
        print("Migration complete!")

if __name__ == "__main__":
    migrate()