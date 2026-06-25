from app import create_app
from app.models import PurchaseBill, db

app = create_app()
with app.app_context():
    print(f"PurchaseBill.is_approved: {hasattr(PurchaseBill, 'is_approved')}")
    try:
        # Try a query
        first_bill = PurchaseBill.query.first()
        if first_bill:
            print(f"First bill is_approved: {first_bill.is_approved}")
        else:
            print("No bills found to test.")
    except Exception as e:
        print(f"Query failed: {e}")
