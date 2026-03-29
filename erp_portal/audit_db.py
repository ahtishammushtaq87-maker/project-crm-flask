import os
import sys

# Add the current directory to path
sys.path.append(os.getcwd())

from app import create_app, db
from app.models import Product, SaleItem, PurchaseItem, StockMovement, Sale, PurchaseBill

app = create_app()

with app.app_context():
    print("--- Database Audit ---")
    print(f"Total Sales: {Sale.query.count()}")
    print(f"Total PurchaseBills: {PurchaseBill.query.count()}")
    print(f"Total SaleItems: {SaleItem.query.count()}")
    print(f"Total PurchaseItems: {PurchaseItem.query.count()}")
    print(f"Total StockMovements: {StockMovement.query.count()}")
    
    # Check specific problem product
    product_name = "Mechanical Keyboard"
    product = Product.query.filter_by(name=product_name).first()
    
    if product:
        print(f"\nAudit for '{product_name}' (ID: {product.id}):")
        print(f"Sale items count: {len(product.sale_items)}")
        print(f"Purchase items count: {len(product.purchase_items)}")
        print(f"Stock movements count: {len(product.stock_movements)}")
        
        if product.sale_items:
            print("Remaining SaleItems:")
            for item in product.sale_items:
                print(f"  Item ID: {item.id}, Sale ID: {item.sale_id}")
                
        if product.purchase_items:
            print("Remaining PurchaseItems:")
            for item in product.purchase_items:
                print(f"  Item ID: {item.id}, Bill ID: {item.bill_id}")

        if product.stock_movements:
            print("Remaining StockMovements:")
            for move in product.stock_movements:
                print(f"  Move ID: {move.id}, Type: {move.movement_type}, Ref: {move.reference_type}#{move.reference_id}")
    else:
        print(f"\nProduct '{product_name}' not found.")
