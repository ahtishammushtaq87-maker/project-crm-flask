from app import create_app, db
from app.models import (
    User, Product, Vendor, Customer, Sale, PurchaseBill, 
    SaleItem, PurchaseItem, Transaction, Expense, StockMovement, Company, InvoiceSettings, ExpenseCategory
)
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from sqlalchemy import inspect, text
import os
import random

app = create_app()

with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database create_all: {e}")

@ app.shell_context_processor
def make_shell_context():
    """Add database models to Flask shell context"""
    return {
        'db': db,
        'User': User,
        'Product': Product,
        'Vendor': Vendor,
        'Customer': Customer,
        'Sale': Sale,
        'PurchaseBill': PurchaseBill,
        'SaleItem': SaleItem,
        'PurchaseItem': PurchaseItem,
        'Transaction': Transaction,
        'Expense': Expense,
        'StockMovement': StockMovement,
        'Company': Company,
        'InvoiceSettings': InvoiceSettings
    }

def init_db():
    """Initialize database with default data and sample records"""
    with app.app_context():
        # Create all tables
        db.create_all()
        # Ensure sales table has vendor_id field (migration for existing DB)
        insp = inspect(db.engine)
        if 'sales' in insp.get_table_names():
            col_names = [c['name'] for c in insp.get_columns('sales')]
            if 'vendor_id' not in col_names:
                print('Adding vendor_id to sales table schema (migration)')
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE sales ADD COLUMN vendor_id INTEGER'))
                    conn.commit()
            else:
                print('sales.vendor_id already present')
        # SQLite schema migration for new vendor_id in sales
        print("Database tables created successfully!")
        
        # Check if database is already initialized (if users exist, we skip sample data)
        db_is_initialized = User.query.first() is not None
        
        # Create default admin user if no admin exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@erp.com',
                role='admin',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            print("Admin user created (username: admin, password: admin123)")
            db.session.commit() # Commit admin so we know it's initialized

        # Only create sample data if the database was NOT previously initialized
        if not db_is_initialized:
            print("Fresh database detected. Populating sample data...")
            
            # Create sample vendors
            sample_vendors = [
                Vendor(name='Tech Supplies Co.', email='info@techsupplies.com', 
                       phone='+1-555-0101', address='123 Tech Street, Silicon Valley, CA',
                       gst_number='GST123456789', contact_person='John Smith', payment_terms=30),
                Vendor(name='Office Furniture Ltd', email='sales@officefurniture.com',
                       phone='+1-555-0102', address='456 Business Ave, New York, NY',
                       gst_number='GST987654321', contact_person='Sarah Johnson', payment_terms=45),
                Vendor(name='Global Electronics', email='info@globalelectronics.com',
                       phone='+1-555-0103', address='789 Innovation Drive, Austin, TX',
                       gst_number='GST456789123', contact_person='Mike Brown', payment_terms=30),
            ]
            for vendor in sample_vendors:
                db.session.add(vendor)
            print("Sample vendors created")
            
            # Create sample customers
            sample_customers = [
                Customer(name='ABC Corporation', email='accounts@abccorp.com',
                        phone='+1-555-0201', address='100 Corporate Park, Chicago, IL',
                        gst_number='GST111222333', credit_limit=50000),
                Customer(name='XYZ Enterprises', email='purchase@xyz.com',
                        phone='+1-555-0202', address='200 Business Hub, Los Angeles, CA',
                        gst_number='GST444555666', credit_limit=30000),
                Customer(name='Tech Solutions Inc', email='info@techsolutions.com',
                        phone='+1-555-0203', address='300 Tech Park, Seattle, WA',
                        gst_number='GST777888999', credit_limit=25000),
            ]
            for customer in sample_customers:
                db.session.add(customer)
            print("Sample customers created")
            
            # Create sample products
            sample_products = [
                Product(name='Laptop Pro', sku='LAP001', barcode='1234567890123',
                       category='Electronics', brand='TechBrand', unit='pcs',
                       unit_price=999.99, cost_price=699.99, quantity=50,
                       reorder_level=10, min_quantity=5, max_quantity=100,
                       location='A-01', weight=2.5),
                Product(name='Wireless Mouse', sku='MOU001', barcode='1234567890124',
                       category='Electronics', brand='TechBrand', unit='pcs',
                       unit_price=29.99, cost_price=15.99, quantity=200,
                       reorder_level=50, min_quantity=20, max_quantity=500,
                       location='A-02', weight=0.2),
                Product(name='Mechanical Keyboard', sku='KEY001', barcode='1234567890125',
                       category='Electronics', brand='TechBrand', unit='pcs',
                       unit_price=89.99, cost_price=49.99, quantity=75,
                       reorder_level=20, min_quantity=10, max_quantity=200,
                       location='A-03', weight=0.8),
                Product(name='27" Monitor', sku='MON001', barcode='1234567890126',
                       category='Electronics', brand='TechBrand', unit='pcs',
                       unit_price=299.99, cost_price=199.99, quantity=30,
                       reorder_level=8, min_quantity=5, max_quantity=50,
                       location='A-04', weight=5.0),
                Product(name='Office Chair', sku='CHA001', barcode='1234567890127',
                       category='Furniture', brand='ComfortCo', unit='pcs',
                       unit_price=159.99, cost_price=89.99, quantity=25,
                       reorder_level=5, min_quantity=3, max_quantity=40,
                       location='B-01', weight=12.0),
            ]
            for product in sample_products:
                db.session.add(product)
            print("Sample products created")
            
            # Create sample expense categories
            sample_categories = [
                ExpenseCategory(name='Office Supplies', description='Stationery, printer ink, office equipment'),
                ExpenseCategory(name='Travel', description='Transportation, accommodation, meals'),
                ExpenseCategory(name='Utilities', description='Electricity, water, internet, phone'),
                ExpenseCategory(name='Marketing', description='Advertising, promotions, events'),
                ExpenseCategory(name='Professional Services', description='Legal, accounting, consulting'),
                ExpenseCategory(name='Equipment', description='Computers, furniture, machinery'),
                ExpenseCategory(name='Maintenance', description='Repairs, servicing, cleaning'),
                ExpenseCategory(name='Miscellaneous', description='Other expenses'),
            ]
            for category in sample_categories:
                db.session.add(category)
            print("Sample expense categories created")
            
            # Commit to get IDs for vendors/customers/products
            db.session.commit()
            
            # Refresh objects
            vendors = Vendor.query.all()
            customers = Customer.query.all()
            products = Product.query.all()
            
            # Create sample sales (last 30 days)
            for i in range(20):  # Create 20 sample invoices
                customer = random.choice(customers)
                sale_date = datetime.now() - timedelta(days=random.randint(0, 30))
                
                sale = Sale(
                    invoice_number=f"INV-{sale_date.strftime('%Y%m')}-{i+1:04d}",
                    customer_id=customer.id,
                    date=sale_date,
                    due_date=sale_date + timedelta(days=30),
                    tax_rate=10,
                    discount_type=random.choice(['fixed', 'percentage']),
                    discount=random.choice([0, 5, 10, 50, 100]),
                    shipping_charge=random.choice([0, 10, 15, 20]),
                    status=random.choice(['paid', 'unpaid', 'partial']),
                    notes="Sample invoice for demonstration",
                    created_by=1
                )
                
                # Add 1-3 items to each sale
                num_items = random.randint(1, 3)
                for _ in range(num_items):
                    product = random.choice(products)
                    quantity = random.randint(1, 5)
                    unit_price = product.unit_price
                    total = quantity * unit_price
                    
                    sale_item = SaleItem(
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=unit_price,
                        total=total
                    )
                    sale.items.append(sale_item)
                
                # Calculate totals
                sale.calculate_totals()
                
                # Set paid amount based on status
                if sale.status == 'paid':
                    sale.paid_amount = sale.total
                elif sale.status == 'partial':
                    sale.paid_amount = sale.total * random.uniform(0.1, 0.9)
                
                db.session.add(sale)
                
                # Update inventory
                for item in sale.items:
                    product = Product.query.get(item.product_id)
                    product.update_quantity(-item.quantity)
            
            print("Sample sales created")
            
            # Create sample purchase bills
            for i in range(15):  # Create 15 sample purchase bills
                bill_date = datetime.now() - timedelta(days=random.randint(0, 45))
                
                bill = PurchaseBill(
                    bill_number=f"PO-{bill_date.strftime('%Y%m')}-{i+1:04d}",
                    vendor_id=random.choice(vendors).id,
                    date=bill_date,
                    due_date=bill_date + timedelta(days=30),
                    tax_rate=10,
                    discount_type='fixed',
                    discount=random.choice([0, 25, 50, 100]),
                    shipping_charge=random.choice([0, 20, 30, 50]),
                    status=random.choice(['paid', 'unpaid', 'partial']),
                    notes="Sample purchase order",
                    created_by=1
                )
                
                # Add items
                num_items = random.randint(1, 3)
                for _ in range(num_items):
                    product = random.choice(products)
                    quantity = random.randint(5, 20)
                    unit_price = product.cost_price
                    total = quantity * unit_price
                    
                    bill_item = PurchaseItem(
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=unit_price,
                        total=total
                    )
                    bill.items.append(bill_item)
                
                # Calculate totals
                bill.calculate_totals()
                
                # Set paid amount based on status
                if bill.status == 'paid':
                    bill.paid_amount = bill.total
                elif bill.status == 'partial':
                    bill.paid_amount = bill.total * random.uniform(0.1, 0.9)
                
                db.session.add(bill)
                
                # Update inventory (increase stock for purchases)
                for item in bill.items:
                    product = Product.query.get(item.product_id)
                    product.update_quantity(item.quantity)
            
            print("Sample purchase bills created")
            
            # Create default company
            company = Company(
                name='Your Company Name',
                address='123 Business Street\nCity, State 12345\nCountry',
                phone='+1-555-0123',
                email='info@yourcompany.com',
                gst_number='GST123456789',
                pan_number='PAN123456789',
                website='https://www.yourcompany.com',
                bank_name='Your Bank Name',
                account_number='123456789012',
                ifsc_code='BANK0001234',
                account_holder_name='Your Company Name'
            )
            db.session.add(company)
            print("Default company created")
            
            # Create default expense categories (if not already created above)
            existing_cat_names = [c.name for c in ExpenseCategory.query.all()]
            default_categories = [
                ExpenseCategory(name='Office Supplies', description='Stationery, printer ink, office equipment'),
                ExpenseCategory(name='Travel', description='Transportation, accommodation, meals'),
                ExpenseCategory(name='Utilities', description='Electricity, water, internet, phone'),
                ExpenseCategory(name='Marketing', description='Advertising, promotions, events'),
                ExpenseCategory(name='Professional Services', description='Legal, accounting, consulting'),
                ExpenseCategory(name='Equipment', description='Computers, furniture, machinery'),
                ExpenseCategory(name='Maintenance', description='Repairs, servicing, upkeep'),
                ExpenseCategory(name='Miscellaneous', description='Other expenses not categorized'),
            ]
            for category in default_categories:
                if category.name not in existing_cat_names:
                    db.session.add(category)
            
            db.session.commit()
            print("Database initialization completed successfully!")
        else:
            print("Database already contains data. Skipping sample data population.")

        print("Database initialization completed successfully!")
        
        # Print summary
        print("\n=== Database Summary ===")
        print(f"Users: {User.query.count()}")
        print(f"Vendors: {Vendor.query.count()}")
        print(f"Customers: {Customer.query.count()}")
        print(f"Products: {Product.query.count()}")
        print(f"Sales Invoices: {Sale.query.count()}")
        print(f"Purchase Bills: {PurchaseBill.query.count()}")
        print(f"Company: {Company.query.count()}")
        print("========================")

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    from flask import render_template
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    from flask import render_template
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    from flask import jsonify
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Run the application (only when running locally)
if __name__ == "__main__":
    with app.app_context():
        try:
            init_db()  # Initialize database and sample data locally
        except Exception as e:
            print(f"Database initialization error: {e}")

    # Get port from environment variable or default to 5000
    port = int(os.environ.get("PORT", 5000))

    # Run Flask app
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True
    )
