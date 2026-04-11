#!/usr/bin/env python
"""
Comprehensive end-to-end test for BOM versioning and overhead handling
Tests both inventory cost changes and overhead expense operations
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Product, BOM, BOMItem, Expense, User
from app.services.bom_versioning import BOMVersioningService

app = create_app()

def print_header(title):
    print(f"\n{'='*70}")
    print(f"{title}")
    print(f"{'='*70}")

def print_test(num, description):
    print(f"\n[TEST {num}] {description}")

def test_comprehensive_bom_workflow():
    """Comprehensive test of BOM versioning workflow"""
    
    with app.app_context():
        print_header("COMPREHENSIVE BOM VERSIONING TEST")
        
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("❌ Admin user not found")
            return False
        
        print(f"✓ Admin user: {admin.username} (ID: {admin.id})")
        
        # ============================================================
        # PART 1: CREATE TEST DATA
        # ============================================================
        print_header("PART 1: Creating Test Data")
        
        # Create products
        components = []
        for i in range(2):
            name = f'Component-{i+1}'
            existing = Product.query.filter_by(name=name).first()
            if not existing:
                p = Product(
                    name=name,
                    sku=f'COMP-{i+1:03d}',
                    cost_price=100.0 + (i*50),
                    unit_price=150.0 + (i*75),
                    quantity=100,
                    category='Components'
                )
                db.session.add(p)
            else:
                p = existing
            components.append(p)
        
        # Create finished product
        finished = Product.query.filter_by(name='FinishedProduct-E2E').first()
        if not finished:
            finished = Product(
                name='FinishedProduct-E2E',
                sku='FINISHED-E2E-001',
                cost_price=500.0,
                unit_price=999.99,
                quantity=50,
                category='Finished'
            )
            db.session.add(finished)
        
        db.session.commit()
        print(f"✓ Created {len(components)} components and finished product")
        
        # Create BOM
        bom = BOM.query.filter_by(name='E2E-TestBOM').first()
        if not bom:
            bom = BOM(
                name='E2E-TestBOM',
                product_id=finished.id,
                is_active=True
            )
            db.session.add(bom)
            db.session.commit()
        
        # Clear existing items
        BOMItem.query.filter_by(bom_id=bom.id).delete()
        db.session.commit()
        
        # Add components to BOM
        for i, comp in enumerate(components):
            item = BOMItem(
                bom_id=bom.id,
                component_id=comp.id,
                quantity=i + 2,
                unit_cost=comp.cost_price,
                shipping_per_unit=5.0
            )
            db.session.add(item)
        
        db.session.commit()
        print(f"✓ Created BOM with {len(components)} components")
        
        # ============================================================
        # PART 2: TEST INVENTORY COST CHANGE
        # ============================================================
        print_header("PART 2: Test Inventory Cost Changes")
        
        print_test(1, "Change component cost")
        print(f"   Component before: Cost = Rs {components[0].cost_price}, BOM Version = {bom.version}")
        
        old_cost = components[0].cost_price
        new_cost = old_cost + 50
        components[0].cost_price = new_cost
        db.session.commit()
        
        # Trigger BOM versioning
        updated = BOMVersioningService.check_and_update_bom_for_cost_changes(
            product_id=components[0].id,
            created_by_id=admin.id
        )
        
        db.session.refresh(bom)
        print(f"   Component after: Cost = Rs {components[0].cost_price}, BOM Version = {bom.version}")
        
        if len(updated) > 0 and bom.version != 'v1':
            print(f"   ✅ PASS: BOM versioned from v1 to {bom.version}")
            v_after_cost_change = bom.version
        else:
            print(f"   ❌ FAIL: BOM should have new version")
            return False
        
        # ============================================================
        # PART 3: TEST OVERHEAD EXPENSE OPERATIONS
        # ============================================================
        print_header("PART 3: Test Overhead Expense Operations")
        
        print_test(2, "Add overhead expense")
        print(f"   BOM overhead before: Rs {bom.overhead_cost}, Version = {bom.version}")
        
        exp1 = Expense(
            expense_number='E2E-EXP-001',
            category_id=1,
            description='E2E Test Overhead 1',
            amount=250.0,
            payment_method='cash',
            is_bom_overhead=True,
            bom_id=bom.id
        )
        db.session.add(exp1)
        db.session.commit()
        
        # Recalculate overhead
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="Test overhead added",
            change_type='overhead_added',
            created_by_id=admin.id,
            recalculate_overhead=True
        )
        
        db.session.refresh(bom)
        print(f"   BOM overhead after: Rs {bom.overhead_cost}, Version = {bom.version}")
        
        if bom.overhead_cost == 250.0:
            print(f"   ✅ PASS: Overhead updated to Rs 250.0")
        else:
            print(f"   ❌ FAIL: Expected overhead Rs 250.0, got {bom.overhead_cost}")
            return False
        
        v_after_exp1 = bom.version
        
        print_test(3, "Add second overhead expense")
        exp2 = Expense(
            expense_number='E2E-EXP-002',
            category_id=1,
            description='E2E Test Overhead 2',
            amount=150.0,
            payment_method='cash',
            is_bom_overhead=True,
            bom_id=bom.id
        )
        db.session.add(exp2)
        db.session.commit()
        
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="Test overhead added",
            change_type='overhead_added',
            created_by_id=admin.id,
            recalculate_overhead=True
        )
        
        db.session.refresh(bom)
        print(f"   BOM overhead after: Rs {bom.overhead_cost}, Version = {bom.version}")
        
        if bom.overhead_cost == 400.0:  # 250 + 150
            print(f"   ✅ PASS: Overhead updated to Rs 400.0 (250+150)")
        else:
            print(f"   ❌ FAIL: Expected overhead Rs 400.0, got {bom.overhead_cost}")
            return False
        
        v_after_exp2 = bom.version
        
        print_test(4, "Uncheck BOM Overhead on first expense (simulate edit unchecking)")
        exp1.is_bom_overhead = False
        db.session.commit()
        
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="Test overhead removed",
            change_type='overhead_added',
            created_by_id=admin.id,
            recalculate_overhead=True
        )
        
        db.session.refresh(bom)
        print(f"   BOM overhead after: Rs {bom.overhead_cost}, Version = {bom.version}")
        
        if bom.overhead_cost == 150.0:  # Only exp2 is overhead
            print(f"   ✅ PASS: Overhead correctly updated to Rs 150.0")
        else:
            print(f"   ❌ FAIL: Expected overhead Rs 150.0, got {bom.overhead_cost}")
            return False
        
        v_after_uncheck = bom.version
        
        print_test(5, "Delete overhead expense")
        db.session.delete(exp2)
        db.session.commit()
        
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="Test overhead deleted",
            change_type='overhead_added',
            created_by_id=admin.id,
            recalculate_overhead=True
        )
        
        db.session.refresh(bom)
        print(f"   BOM overhead after: Rs {bom.overhead_cost}, Version = {bom.version}")
        
        if bom.overhead_cost == 0.0:  # No overhead left
            print(f"   ✅ PASS: Overhead correctly recalculated to Rs 0.0")
        else:
            print(f"   ❌ FAIL: Expected overhead Rs 0.0, got {bom.overhead_cost}")
            return False
        
        v_final = bom.version
        
        # ============================================================
        # RESULTS
        # ============================================================
        print_header("TEST RESULTS")
        
        print("\n✅ All tests passed!")
        print(f"\nVersion progression:")
        print(f"  v1 (initial)")
        print(f"  → {v_after_cost_change} (component cost changed)")
        print(f"  → {v_after_exp1} (overhead added)")
        print(f"  → {v_after_exp2} (overhead added)")
        print(f"  → {v_after_uncheck} (overhead removed)")
        print(f"  → {v_final} (overhead deleted)")
        
        print(f"\nFinal BOM State:")
        print(f"  Name: {bom.name}")
        print(f"  Version: {bom.version}")
        print(f"  Overhead Cost: Rs {bom.overhead_cost}")
        print(f"  Total Cost: Rs {bom.total_cost}")
        
        return True

if __name__ == '__main__':
    try:
        success = test_comprehensive_bom_workflow()
        if success:
            print("\n" + "="*70)
            print("✅ COMPREHENSIVE E2E TEST PASSED")
            print("="*70)
            sys.exit(0)
        else:
            print("\n" + "="*70)
            print("❌ COMPREHENSIVE E2E TEST FAILED")
            print("="*70)
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
