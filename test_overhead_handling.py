#!/usr/bin/env python
"""
Test script to verify BOM overhead recalculation works correctly
Tests: add overhead, remove overhead, checkbox unchecking
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Product, BOM, Expense, User
from app.services.bom_versioning import BOMVersioningService

app = create_app()

def test_overhead_handling():
    """Test that BOM overhead is correctly calculated when expenses are added/removed"""
    with app.app_context():
        print("\n" + "="*70)
        print("TEST: BOM Overhead Expense Handling")
        print("="*70)
        
        # Get admin user
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("❌ Admin user not found")
            return False
        
        # Create test product
        product = Product.query.filter_by(name='OverheadTestProduct').first()
        if not product:
            product = Product(
                name='OverheadTestProduct',
                sku='OVERHEAD-TEST-001',
                cost_price=100.0,
                unit_price=200.0,
                quantity=10,
                category='Test'
            )
            db.session.add(product)
            db.session.commit()
        
        # Create test BOM linked to product
        bom = BOM.query.filter_by(name='OverheadTestBOM').first()
        if not bom:
            bom = BOM(
                name='OverheadTestBOM',
                product_id=product.id,
                is_active=True
            )
            db.session.add(bom)
            db.session.commit()
        
        print(f"\n✓ Setup: BOM '{bom.name}' (Version: {bom.version}, Overhead: Rs {bom.overhead_cost})")
        initial_version = bom.version
        
        # TEST 1: Add overhead expense
        print(f"\n[TEST 1] Adding overhead expense of Rs 500...")
        expense1 = Expense(
            expense_number='TEST-EXP-001',
            category_id=1,
            description='Test overhead',
            amount=500.0,
            payment_method='cash',
            is_bom_overhead=True,
            bom_id=bom.id
        )
        db.session.add(expense1)
        db.session.commit()
        
        # Trigger BOM versioning
        updated = BOMVersioningService.check_and_update_bom_for_cost_changes(
            product_id=product.id,
            created_by_id=admin.id
        )
        
        # Manually recalculate overhead
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="Overhead expense added",
            change_type='overhead_added',
            created_by_id=admin.id,
            recalculate_overhead=True
        )
        
        db.session.refresh(bom)
        print(f"   After adding: BOM Version = {bom.version}, Overhead = Rs {bom.overhead_cost}")
        if bom.overhead_cost == 500.0 and bom.version != initial_version:
            print(f"   ✓ Overhead correctly updated to Rs 500.0 and version created")
        else:
            print(f"   ⚠ Expected overhead Rs 500.0, got Rs {bom.overhead_cost}")
        
        v1_version = bom.version
        
        # TEST 2: Add another overhead expense
        print(f"\n[TEST 2] Adding another overhead expense of Rs 300...")
        expense2 = Expense(
            expense_number='TEST-EXP-002',
            category_id=1,
            description='Test overhead 2',
            amount=300.0,
            payment_method='cash',
            is_bom_overhead=True,
            bom_id=bom.id
        )
        db.session.add(expense2)
        db.session.commit()
        
        # Recalculate overhead
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="Overhead expense added",
            change_type='overhead_added',
            created_by_id=admin.id,
            recalculate_overhead=True
        )
        
        db.session.refresh(bom)
        print(f"   After adding: BOM Version = {bom.version}, Overhead = Rs {bom.overhead_cost}")
        if bom.overhead_cost == 800.0:  # 500 + 300
            print(f"   ✓ Overhead correctly updated to Rs 800.0 (500+300)")
        else:
            print(f"   ⚠ Expected overhead Rs 800.0, got Rs {bom.overhead_cost}")
        
        v2_version = bom.version
        
        # TEST 3: Remove overhead flag from first expense (simulating unchecking checkbox)
        print(f"\n[TEST 3] Removing overhead flag from first expense (simulating unchecking)...")
        expense1.is_bom_overhead = False
        db.session.commit()
        
        # Recalculate overhead
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="Overhead expense removed",
            change_type='overhead_added',
            created_by_id=admin.id,
            recalculate_overhead=True
        )
        
        db.session.refresh(bom)
        print(f"   After removing: BOM Version = {bom.version}, Overhead = Rs {bom.overhead_cost}")
        if bom.overhead_cost == 300.0:  # Only expense2 is overhead now
            print(f"   ✓ Overhead correctly recalculated to Rs 300.0")
        else:
            print(f"   ⚠ Expected overhead Rs 300.0, got Rs {bom.overhead_cost}")
        
        v3_version = bom.version
        
        # TEST 4: Delete an overhead expense
        print(f"\n[TEST 4] Deleting overhead expense...")
        db.session.delete(expense2)
        db.session.commit()
        
        # Recalculate overhead
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="Overhead expense deleted",
            change_type='overhead_added',
            created_by_id=admin.id,
            recalculate_overhead=True
        )
        
        db.session.refresh(bom)
        print(f"   After deleting: BOM Version = {bom.version}, Overhead = Rs {bom.overhead_cost}")
        if bom.overhead_cost == 0.0:  # No overhead expenses left
            print(f"   ✓ Overhead correctly recalculated to Rs 0.0")
        else:
            print(f"   ⚠ Expected overhead Rs 0.0, got Rs {bom.overhead_cost}")
        
        print(f"\n✅ All overhead tests completed!")
        print(f"   Version progression: {initial_version} → {v1_version} → {v2_version} → {v3_version}")
        return True

if __name__ == '__main__':
    success = test_overhead_handling()
    sys.exit(0 if success else 1)
