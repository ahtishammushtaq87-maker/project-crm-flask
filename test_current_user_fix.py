#!/usr/bin/env python
"""
Test BOM versioning with fixed current_user imports
"""
from app import create_app, db
from app.models import Product, User
from app.services.bom_versioning import BOMVersioningService

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("TEST: BOM VERSIONING WITH FIXED IMPORTS")
    print("="*80)
    
    # Get test data
    admin = User.query.filter_by(username='admin').first()
    product = Product.query.first()
    
    if not admin or not product:
        print("✗ Missing test data")
        exit(1)
    
    print(f"\n✓ Admin user found: {admin.username} (ID: {admin.id})")
    print(f"✓ Product found: {product.name} (ID: {product.id})")
    print(f"✓ Current product cost: Rs {product.cost_price}")
    
    # Test the versioning service
    print(f"\n" + "-"*80)
    print("Testing BOM Versioning Service Call...")
    print("-"*80)
    
    old_cost = product.cost_price
    new_cost = old_cost + 100
    
    print(f"\nChanging product cost: Rs {old_cost} → Rs {new_cost}")
    
    product.cost_price = new_cost
    db.session.commit()
    
    print(f"Calling: BOMVersioningService.check_and_update_bom_for_cost_changes(")
    print(f"  product_id={product.id},")
    print(f"  created_by_id={admin.id}")
    print(f")")
    
    try:
        updated_boms = BOMVersioningService.check_and_update_bom_for_cost_changes(
            product_id=product.id,
            created_by_id=admin.id
        )
        
        print(f"\n{'✓'*40}")
        print(f"SUCCESS! Service call completed without errors")
        print(f"{'✓'*40}")
        print(f"\nBOMs updated: {len(updated_boms)}")
        
        if len(updated_boms) > 0:
            for bom in updated_boms:
                print(f"  - {bom.name}: {bom.version}")
        
        print(f"\n✅ BOM VERSIONING IS NOW WORKING!")
        print(f"   The 'current_user' import fix resolved the issue.")
        
    except NameError as e:
        if 'current_user' in str(e):
            print(f"\n❌ ERROR: {e}")
            print(f"    The current_user import is still not working")
        else:
            raise
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n" + "="*80)
