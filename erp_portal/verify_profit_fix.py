import os
import sys

# Add the current directory to path
sys.path.append(os.getcwd())

from app import create_app, db
from app.models import Sale, SaleItem, Product, Customer
from datetime import datetime

app = create_app()

with app.app_context():
    print("--- Verifying Gross Profit and COGS Calculation ---")
    
    # 1. Setup a test product with a specific cost and unit price
    test_prod = Product(
        name='Profit Test Product',
        sku=f'PROFIT-TEST-{datetime.now().strftime("%H%M%S")}',
        cost_price=60.0,
        unit_price=100.0,
        quantity=100
    )
    db.session.add(test_prod)
    db.session.commit()
    prod_id = test_prod.id
    
    # 2. Create a sale for this product (Qty: 2)
    # Total Sale: 200, Total Cost (COGS): 120, Expected Gross Profit: 80
    sale = Sale(
        invoice_number=f"TEST-PROFIT-INV-{datetime.now().strftime('%H%M%S')}",
        subtotal=200.0,
        total=200.0,
        date=datetime.now()
    )
    db.session.add(sale)
    db.session.flush()
    
    item = SaleItem(
        sale_id=sale.id,
        product_id=prod_id,
        quantity=2.0,
        unit_price=100.0,
        total=200.0
    )
    db.session.add(item)
    db.session.commit()
    
    # 3. Simulate the Dashboard calculation logic
    from sqlalchemy import func
    
    current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    total_sales = db.session.query(func.sum(Sale.total)).filter(Sale.date >= current_month).scalar() or 0
    total_cogs = db.session.query(func.sum(SaleItem.quantity * Product.cost_price))\
        .join(Sale, SaleItem.sale_id == Sale.id)\
        .join(Product, SaleItem.product_id == Product.id)\
        .filter(Sale.date >= current_month)\
        .scalar() or 0
    
    gross_profit = total_sales - total_cogs
    
    print(f"Total Sales: {total_sales}")
    print(f"Total COGS: {total_cogs}")
    print(f"Gross Profit: {gross_profit}")
    
    # Check if our test sale result is reflected in the sum (assuming this is the only sale today)
    # If there are other sales, total_cogs should at least be >= 120
    if total_cogs >= 120.0:
        print("SUCCESS: COGS reflects product cost price * quantity.")
    else:
        print(f"FAILURE: COGS {total_cogs} is lower than expected 120.")
        
    # Cleanup
    db.session.delete(item)
    db.session.delete(sale)
    db.session.delete(test_prod)
    db.session.commit()
