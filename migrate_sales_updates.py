"""
Migration script to add new columns to sales table and create customer_advances table
"""
from app import create_app, db
from sqlalchemy import inspect, text

app = create_app()

with app.app_context():
    try:
        inspector = inspect(db.engine)
        
        print("=" * 60)
        print("DATABASE MIGRATION: Adding Sales & Customer Advance Updates")
        print("=" * 60)
        
        # Check if columns already exist
        sales_columns = [c['name'] for c in inspector.get_columns('sales')]
        sale_items_columns = [c['name'] for c in inspector.get_columns('sale_items')]
        
        print("\n1. Checking Sales table...")
        
        with db.engine.connect() as conn:
            # Add delivery_charge column
            if 'delivery_charge' not in sales_columns:
                print("   - Adding delivery_charge column...")
                conn.execute(text("ALTER TABLE sales ADD COLUMN delivery_charge FLOAT DEFAULT 0"))
                conn.commit()
                print("     SUCCESS: delivery_charge added")
            else:
                print("     OK: delivery_charge already exists")
            
            # Add advance_applied column
            if 'advance_applied' not in sales_columns:
                print("   - Adding advance_applied column...")
                conn.execute(text("ALTER TABLE sales ADD COLUMN advance_applied FLOAT DEFAULT 0"))
                conn.commit()
                print("     SUCCESS: advance_applied added")
            else:
                print("     OK: advance_applied already exists")
        
        print("\n2. Checking Sale Items table...")
        
        with db.engine.connect() as conn:
            if 'delivery_fee' not in sale_items_columns:
                print("   - Adding delivery_fee column...")
                conn.execute(text("ALTER TABLE sale_items ADD COLUMN delivery_fee FLOAT DEFAULT 0"))
                conn.commit()
                print("     SUCCESS: delivery_fee added")
            else:
                print("     OK: delivery_fee already exists")
        
        # Check if customer_advances table exists
        tables = [t for t in inspector.get_table_names()]
        print("\n2. Checking customer_advances table...")
        
        if 'customer_advances' not in tables:
            print("   - Creating customer_advances table...")
            db.create_all()
            print("     SUCCESS: customer_advances table created")
        else:
            print("     OK: customer_advances table already exists")
        
        # Check if Customer has advances relationship
        print("\n3. Checking Customer model updates...")
        from app.models import Customer, CustomerAdvance
        customer = Customer()
        if hasattr(customer, 'advances'):
            print("     OK: Customer.advances relationship exists")
        else:
            print("     WARNING: Customer.advances relationship missing")
        
        print("\n" + "=" * 60)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nNew features added:")
        print("  ✓ Delivery Charge field in Sales Invoices")
        print("  ✓ Advance Applied field in Sales Invoices")
        print("  ✓ CustomerAdvance model for tracking customer advances")
        print("  ✓ Customer profile enhanced with advance management")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\nERROR during migration: {e}")
        print("Please check the error and try again.")
        import traceback
        traceback.print_exc()
