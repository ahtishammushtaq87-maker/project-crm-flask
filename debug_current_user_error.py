#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug the current_user error in detail
"""
from app import create_app, db
from app.models import Product, User
from app.services.bom_versioning import BOMVersioningService
import traceback
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("DEBUG: Tracing current_user Error")
    print("="*80)
    
    # Get test data
    admin = User.query.filter_by(username='admin').first()
    product = Product.query.first()
    
    if not admin or not product:
        print("❌ Missing test data")
        exit(1)
    
    print(f"\n✓ Admin user: {admin.username} (ID: {admin.id})")
    print(f"✓ Product: {product.name}")
    
    # Simulate what the route does
    print(f"\n" + "-"*80)
    print("Simulating inventory.edit_product() flow:")
    print("-"*80)
    
    old_cost = product.cost_price
    new_cost = old_cost + 100
    
    print(f"\n1. Storing old_cost: {old_cost}")
    print(f"2. Updating product.cost_price: {new_cost}")
    
    product.cost_price = new_cost
    db.session.commit()
    
    print(f"3. Comparing: old_cost ({old_cost}) != new_cost ({product.cost_price})?")
    
    if old_cost != product.cost_price:
        print(f"   ✓ Cost changed, calling BOMVersioningService")
        
        print(f"\n4. Calling BOMVersioningService.check_and_update_bom_for_cost_changes(")
        print(f"     product_id={product.id},")
        print(f"     created_by_id={admin.id}")
        print(f"   )")
        
        try:
            updated_boms = BOMVersioningService.check_and_update_bom_for_cost_changes(
                product_id=product.id,
                created_by_id=admin.id
            )
            print(f"\n✅ Service call succeeded!")
            print(f"   BOMs updated: {len(updated_boms)}")
            
        except NameError as e:
            print(f"\n❌ NameError occurred: {e}")
            print(f"\nFull traceback:")
            traceback.print_exc()
            
            print(f"\n" + "="*80)
            print("ANALYSIS:")
            print("="*80)
            print(f"""
The error 'current_user' is not defined is happening INSIDE a function.

This suggests:
1. The error is NOT in the route (we already imported current_user there)
2. The error might be in a nested function or imported module
3. The error might be in exception handling code

Let me check if the error is coming from somewhere else...
            """)
            
        except Exception as e:
            print(f"\n⚠️  Other error occurred: {type(e).__name__}: {e}")
            print(f"\nFull traceback:")
            traceback.print_exc()
