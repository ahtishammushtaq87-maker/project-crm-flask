#!/usr/bin/env python
"""
Simulate editing a product cost and see if BOM versioning is triggered
"""
from app import create_app, db
from app.models import Product, BOM, User
from app.services.bom_versioning import BOMVersioningService

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("TEST: Edit Product Cost → Check BOM Versioning")
    print("="*80)
    
    # Get test user
    user = User.query.filter_by(username='admin').first()
    if not user:
        user = User.query.first()
    
    if not user:
        print("✗ No user found")
        exit(1)
    
    print(f"\nUser: {user.username} (ID: {user.id})")
    
    # Get first product with a BOM item
    product = Product.query.join(BOM.items).first()
    if not product:
        print("✗ No product found in any BOM")
        exit(1)
    
    print(f"\nProduct: {product.name} (ID: {product.id})")
    print(f"Current cost_price: Rs {product.cost_price}")
    
    # Simulate editing the product
    old_cost = product.cost_price
    new_cost = old_cost + 100  # Increase by Rs 100
    
    print(f"\n" + "-"*80)
    print("SIMULATING INVENTORY EDIT:")
    print("-"*80)
    
    print(f"Old cost: Rs {old_cost}")
    print(f"New cost: Rs {new_cost}")
    
    # This is what the inventory edit route does
    product.cost_price = new_cost
    db.session.commit()
    print(f"\n✓ Product cost updated in database")
    
    # Now trigger the versioning service
    print(f"\n" + "-"*80)
    print("TRIGGERING BOM VERSIONING SERVICE:")
    print("-"*80)
    
    if old_cost != new_cost:
        print(f"\n✓ Cost change detected ({old_cost} → {new_cost})")
        print(f"Calling: BOMVersioningService.check_and_update_bom_for_cost_changes()")
        
        updated_boms = BOMVersioningService.check_and_update_bom_for_cost_changes(
            product_id=product.id,
            created_by_id=user.id
        )
        
        print(f"\n{'='*80}")
        print(f"RESULT: {len(updated_boms)} BOM(s) updated")
        print(f"{'='*80}")
        
        for bom in updated_boms:
            print(f"\n✓ BOM {bom.id}: {bom.name}")
            print(f"  New version: {bom.version}")
            print(f"  Total cost: Rs {bom.total_cost}")
        
        if len(updated_boms) > 0:
            print(f"\n{'✓'*40}")
            print(f"SUCCESS! BOM versioning WORKED!")
            print(f"{'✓'*40}")
        else:
            print(f"\n{'✗'*40}")
            print(f"FAILED! No BOMs were updated!")
            print(f"{'✗'*40}")
    else:
        print(f"✗ No cost change detected")
    
    print("\n" + "="*80)
