#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test the Reset BOM Overhead functionality
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Fix for Windows terminal encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app, db
from app.models import Product, BOM, Expense, User
from app.services.bom_versioning import BOMVersioningService

app = create_app()

def test_reset_bom_overhead():
    with app.app_context():
        print("\n" + "="*70)
        print("TEST: Reset BOM Overhead Functionality")
        print("="*70)
        
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("FAIL: Admin user not found")
            return False
        
        # Create test product and BOM
        product = Product.query.filter_by(name='ResetTestProduct').first()
        if not product:
            product = Product(
                name='ResetTestProduct',
                sku='RESET-TEST-001',
                cost_price=100.0,
                unit_price=200.0,
                quantity=10,
                category='Test'
            )
            db.session.add(product)
            db.session.commit()
        
        bom = BOM.query.filter_by(name='ResetTestBOM').first()
        if not bom:
            bom = BOM(
                name='ResetTestBOM',
                product_id=product.id,
                is_active=True
            )
            db.session.add(bom)
            db.session.commit()
        
        print("\nOK: Setup: BOM 'ResetTestBOM' created")
        print("   Initial: Version={}, Overhead=Rs {}".format(bom.version, bom.overhead_cost))
        
        # Step 1: Add overhead expenses
        print("\n[STEP 1] Adding overhead expenses...")
        exp1 = Expense(
            expense_number='RESET-EXP-001',
            category_id=1,
            description='Overhead 1',
            amount=100.0,
            payment_method='cash',
            is_bom_overhead=True,
            bom_id=bom.id
        )
        exp2 = Expense(
            expense_number='RESET-EXP-002',
            category_id=1,
            description='Overhead 2',
            amount=150.0,
            payment_method='cash',
            is_bom_overhead=True,
            bom_id=bom.id
        )
        db.session.add(exp1)
        db.session.add(exp2)
        db.session.commit()
        
        # Create BOM version
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="Overhead expenses added",
            change_type='overhead_added',
            created_by_id=admin.id,
            recalculate_overhead=True
        )
        
        db.session.refresh(bom)
        print("   After adding: Version={}, Overhead=Rs {}".format(bom.version, bom.overhead_cost))
        
        if bom.overhead_cost != 250.0:
            print("   FAIL: Expected overhead Rs 250.0, got Rs {}".format(bom.overhead_cost))
            return False
        
        print("   PASS: Overhead correctly updated to Rs 250.0")
        
        # Step 2: Mark expenses as non-overhead (simulating reset)
        print("\n[STEP 2] Resetting BOM overhead (marking expenses as non-overhead)...")
        exp1.is_bom_overhead = False
        exp2.is_bom_overhead = False
        db.session.commit()
        
        # Create new BOM version with recalculated overhead
        BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason="BOM overhead reset: 2 overhead expenses cleared",
            change_type='overhead_added',
            created_by_id=admin.id,
            recalculate_overhead=True
        )
        
        db.session.refresh(bom)
        print("   After reset: Version={}, Overhead=Rs {}".format(bom.version, bom.overhead_cost))
        
        if bom.overhead_cost != 0.0:
            print("   FAIL: Expected overhead Rs 0.0, got Rs {}".format(bom.overhead_cost))
            return False
        
        print("   PASS: Overhead correctly reset to Rs 0.0")
        
        # Step 3: Verify expenses are no longer marked as overhead
        print("\n[STEP 3] Verifying expenses...")
        exp1_check = Expense.query.get(exp1.id)
        exp2_check = Expense.query.get(exp2.id)
        
        if exp1_check.is_bom_overhead or exp2_check.is_bom_overhead:
            print("   FAIL: Expenses should not be marked as overhead")
            return False
        
        print("   PASS: Both expenses correctly marked as non-overhead")
        
        print("\nOK: Reset BOM Overhead test PASSED!")
        print("\nVersion history: v1 -> {}".format(bom.version))
        print("Final BOM state: Overhead=Rs {}, Version={}".format(bom.overhead_cost, bom.version))
        
        return True

if __name__ == '__main__':
    try:
        success = test_reset_bom_overhead()
        sys.exit(0 if success else 1)
    except Exception as e:
        print("\nFAIL: ERROR: {}".format(str(e)))
        import traceback
        traceback.print_exc()
        sys.exit(1)
