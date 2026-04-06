from app import create_app, db
from app.models import Staff, SalaryAdvance, SalaryPayment

app = create_app()
with app.app_context():
    try:
        # Create all tables (only creates tables that don't exist)
        db.create_all()
        print("Database tables for Salary Module created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")
