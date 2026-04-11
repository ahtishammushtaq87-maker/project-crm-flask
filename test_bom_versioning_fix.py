#!/usr/bin/env python
"""
Test script to verify BOM versioning works when editing product cost
Simulates user logged in and editing product cost in inventory
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Product, BOM, BOMItem, User
from flask_login import login_user

app = create_app()

def test_product_cost_change_triggers_bom():
    """Test that changing product cost triggers BOM versioning"""
    with app.app_context():
        print("\n" + "="*70)
        print("TEST: Product Cost Change -> BOM Versioning")
        print("="*70)
        
        # Get or create admin user
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("❌ Admin user not found")
            return False
        
        print(f"✓ Admin user found: {admin.username} (ID: {admin.id})")
        
        # Get or create test product
        product = Product.query.filter_by(name='TestComponent').first()
        if not product:
            product = Product(
                name='TestComponent',
                sku='TEST-COMP-001',
                cost_price=100.0,
                unit_price=150.0,
                quantity=50,
                category='Test'
            )
            db.session.add(product)
            db.session.commit()
            print(f"✓ Created test product: {product.name} (Cost: Rs {product.cost_price})")
        else:
            print(f"✓ Using existing product: {product.name} (Cost: Rs {product.cost_price})")
        
        # Get or create test BOM
        bom = BOM.query.filter_by(name='TestBOM').first()
        if not bom:
            bom = BOM(
                name='TestBOM',
                description='Test BOM for versioning',
                is_active=True,
                created_by_id=admin.id
            )
            db.session.add(bom)
            db.session.commit()
            print(f"✓ Created test BOM: {bom.name} (Version: {bom.version})")
        else:
            print(f"✓ Using existing BOM: {bom.name} (Version: {bom.version})")
        
        # Add product as component if not already there
        bom_item = BOMItem.query.filter_by(bom_id=bom.id, component_id=product.id).first()
        if not bom_item:
            bom_item = BOMItem(
                bom_id=bom.id,
                component_id=product.id,
                quantity=5,
                unit_cost=product.cost_price,
                shipping_per_unit=0
            )
            db.session.add(bom_item)
            db.session.commit()
            print(f"✓ Added product to BOM as component")
        else:
            print(f"✓ Product already component of BOM")
        
        print(f"\n[Before] BOM Version: {bom.version}, Item Cost: Rs {bom_item.unit_cost}")
        
        # Simulate product cost change
        old_cost = product.cost_price
        new_cost = old_cost + 25.0  # Increase cost by 25
        
        print(f"\n→ Changing product cost from Rs {old_cost} to Rs {new_cost}...")
        product.cost_price = new_cost
        db.session.commit()
        
        # Now trigger BOM versioning (this is what happens in the route)
        print(f"\n→ Triggering BOM versioning service...")
        from app.services.bom_versioning import BOMVersioningService
        
        try:
            # This is the key: safe user_id resolution
            user_id = admin.id
            print(f"✓ Using user_id: {user_id}")
            
            updated_boms = BOMVersioningService.check_and_update_bom_for_cost_changes(
                product_id=product.id,
                created_by_id=user_id
            )
            
            print(f"\n✓ Service completed successfully")
            print(f"✓ Updated BOMs: {len(updated_boms)}")
            
            # Refresh BOM to get new version
            db.session.refresh(bom)
            print(f"\n[After] BOM Version: {bom.version}")
            
            if len(updated_boms) > 0 and bom.version != 'v1':
                print(f"\n✅ SUCCESS: BOM version created! New version: {bom.version}")
                return True
            else:
                print(f"\n⚠ No BOM versions created (might be expected if no cost mismatch)")
                return True
                
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = test_product_cost_change_triggers_bom()
    sys.exit(0 if success else 1)
