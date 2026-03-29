import os
import sys

# Add the current directory to path
sys.path.append(os.getcwd())

from app import create_app, db
from app.models import Sale, SaleItem, PurchaseBill, PurchaseItem, Product, StockMovement

app = create_app()

with app.app_context():
    print("--- Database Repair and Cleanup ---")
    
    # 1. Cleanup orphaned SaleItems
    orphaned_sale_items = SaleItem.query.filter(~SaleItem.sale_id.in_(db.session.query(Sale.id))).all()
    if orphaned_sale_items:
        print(f"Found {len(orphaned_sale_items)} orphaned SaleItem(s). Deleting...")
        for item in orphaned_sale_items:
            db.session.delete(item)
    else:
        print("No orphaned SaleItems found.")
        
    # 2. Cleanup orphaned PurchaseItems
    orphaned_purchase_items = PurchaseItem.query.filter(~PurchaseItem.bill_id.in_(db.session.query(PurchaseBill.id))).all()
    if orphaned_purchase_items:
        print(f"Found {len(orphaned_purchase_items)} orphaned PurchaseItem(s). Deleting...")
        for item in orphaned_purchase_items:
            db.session.delete(item)
    else:
        print("No orphaned PurchaseItems found.")
        
    # 3. Cleanup StockMovements that refer to missing Sales/Purchases
    # Sale movements
    orph_sale_moves = StockMovement.query.filter_by(reference_type='sale').filter(~StockMovement.reference_id.in_(db.session.query(Sale.id))).all()
    # Purchase movements
    orph_purch_moves = StockMovement.query.filter_by(reference_type='purchase').filter(~StockMovement.reference_id.in_(db.session.query(PurchaseBill.id))).all()
    
    total_orph_moves = len(orph_sale_moves) + len(orph_purch_moves)
    if total_orph_moves > 0:
        print(f"Found {total_orph_moves} orphaned StockMovement(s). Deleting...")
        for move in orph_sale_moves + orph_purch_moves:
            db.session.delete(move)
    else:
        print("No orphaned StockMovements found.")

    try:
        db.session.commit()
        print("--- Cleanup Successful! ---")
    except Exception as e:
        db.session.rollback()
        print(f"--- Cleanup Failed: {str(e)} ---")
