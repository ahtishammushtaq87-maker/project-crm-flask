import os
import sys

# Add the current directory to path
sys.path.append(os.getcwd())

from app import create_app, db
from app.models import Product

app = create_app()

with app.app_context():
    product_name = "Mechanical Keyboard"
    product = Product.query.filter_by(name=product_name).first()
    
    if product:
        print(f"Product '{product_name}' found. Attempting deletion...")
        # Check reasons for blocking
        reasons = []
        if product.sale_items: reasons.append(f"{len(product.sale_items)} sale items")
        if product.purchase_items: reasons.append(f"{len(product.purchase_items)} purchase items")
        if product.stock_movements: reasons.append(f"{len(product.stock_movements)} stock movements")
        
        if reasons:
            print(f"FAILURE: Product still has associations: {', '.join(reasons)}")
        else:
            db.session.delete(product)
            db.session.commit()
            print(f"SUCCESS: Product '{product_name}' deleted successfully!")
    else:
        print(f"Product '{product_name}' already gone or not found.")
