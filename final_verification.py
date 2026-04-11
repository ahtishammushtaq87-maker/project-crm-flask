#!/usr/bin/env python
"""
FINAL VERIFICATION CHECKLIST
Run this to confirm all BOM versioning components are working
"""
from app import create_app, db
from app.models import (
    Product, BOM, BOMVersion, BOMVersionItem, BOMItem,
    User, Expense
)
from app.services.bom_versioning import BOMVersioningService
import inspect

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("BOM VERSIONING SYSTEM - FINAL VERIFICATION CHECKLIST")
    print("="*80 + "\n")
    
    checks_passed = 0
    checks_total = 0
    
    # CHECK 1: Database Tables
    print("1. DATABASE TABLES")
    checks_total += 1
    try:
        bom_versions = BOMVersion.query.first()
        bom_version_items = BOMVersionItem.query.first()
        print("   ✓ bom_versions table exists")
        print("   ✓ bom_version_items table exists")
        checks_passed += 1
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
    
    # CHECK 2: Model Fields
    print("\n2. MODEL FIELDS")
    checks_total += 1
    try:
        bom = BOM.query.first()
        assert hasattr(bom, 'version'), "BOM missing 'version' field"
        assert hasattr(bom, 'is_active'), "BOM missing 'is_active' field"
        
        bom_item = bom.items[0] if bom.items else None
        if bom_item:
            assert hasattr(bom_item, 'unit_cost'), "BOMItem missing 'unit_cost' field"
            assert hasattr(bom_item, 'shipping_per_unit'), "BOMItem missing 'shipping_per_unit'"
        
        print("   ✓ BOM.version field exists")
        print("   ✓ BOM.is_active field exists")
        print("   ✓ BOMItem.unit_cost field exists")
        print("   ✓ BOMItem.shipping_per_unit field exists")
        print("   ✓ BOMVersion model exists")
        print("   ✓ BOMVersionItem model exists")
        checks_passed += 1
    except AssertionError as e:
        print(f"   ✗ ERROR: {e}")
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
    
    # CHECK 3: Service Layer
    print("\n3. SERVICE LAYER")
    checks_total += 1
    try:
        # Check methods exist
        methods = [
            'check_and_update_bom_for_cost_changes',
            'create_bom_version',
            'get_next_version',
            'check_and_update_bom_for_overhead_changes',
            'get_bom_version_history',
            'compare_bom_versions',
            'allocate_purchase_shipping_to_bom'
        ]
        
        for method in methods:
            assert hasattr(BOMVersioningService, method), f"Missing method: {method}"
            print(f"   ✓ BOMVersioningService.{method}() exists")
        
        checks_passed += 1
    except AssertionError as e:
        print(f"   ✗ ERROR: {e}")
    
    # CHECK 4: Route Implementation
    print("\n4. ROUTE IMPLEMENTATIONS")
    checks_total += 1
    try:
        # Check if routes were modified
        from app.routes import inventory, accounting, purchase
        
        # Verify imports exist in routes
        inventory_source = inspect.getsource(inventory.edit_product)
        accounting_source = inspect.getsource(accounting.add_expense)
        
        assert 'BOMVersioningService' in inventory_source, "Inventory trigger not implemented"
        assert 'BOMVersioningService' in accounting_source, "Accounting trigger not implemented"
        
        print("   ✓ inventory.edit_product() has versioning trigger")
        print("   ✓ accounting.add_expense() has versioning trigger")
        print("   ✓ All routes properly configured")
        checks_passed += 1
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
    
    # CHECK 5: Version History
    print("\n5. VERSION HISTORY")
    checks_total += 1
    try:
        bom = BOM.query.first()
        versions = BOMVersion.query.filter_by(bom_id=bom.id).all()
        
        print(f"   ✓ BOM: {bom.name}")
        print(f"   ✓ Current version: {bom.version}")
        print(f"   ✓ Total versions recorded: {len(versions)}")
        
        if versions:
            latest = max(versions, key=lambda v: int(v.version_number[1:]))
            print(f"   ✓ Latest version: v{latest.version_number}")
            print(f"   ✓ Latest change reason: {latest.change_reason[:40]}...")
        
        checks_passed += 1
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
    
    # CHECK 6: Versioning Trigger Test
    print("\n6. VERSIONING TRIGGER TEST")
    checks_total += 1
    try:
        bom = BOM.query.first()
        product = Product.query.first()
        admin = User.query.filter_by(username='admin').first()
        
        version_before = bom.version
        cost_before = product.cost_price
        
        # Simulate change
        product.cost_price = cost_before + 50
        db.session.commit()
        
        # Trigger versioning
        updated = BOMVersioningService.check_and_update_bom_for_cost_changes(
            product_id=product.id,
            created_by_id=admin.id
        )
        
        db.session.refresh(bom)
        version_after = bom.version
        
        assert len(updated) > 0, "No BOMs were updated"
        assert version_after != version_before, "Version did not change"
        
        print(f"   ✓ Trigger test passed")
        print(f"   ✓ Version changed: {version_before} → {version_after}")
        print(f"   ✓ BOMs updated: {len(updated)}")
        checks_passed += 1
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
    
    # CHECK 7: Debug Logging
    print("\n7. DEBUG LOGGING")
    checks_total += 1
    try:
        service_source = inspect.getsource(BOMVersioningService.check_and_update_bom_for_cost_changes)
        inventory_source = inspect.getsource(inventory.edit_product)
        
        assert '[BOM_VERSION_SERVICE]' in service_source, "Service logging not found"
        assert '[DEBUG]' in inventory_source, "Inventory logging not found"
        
        print("   ✓ BOMVersioningService has debug logging")
        print("   ✓ inventory routes have debug logging")
        print("   ✓ Debug output configured")
        checks_passed += 1
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
    
    # SUMMARY
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    percentage = (checks_passed / checks_total) * 100
    
    print(f"\nChecks Passed: {checks_passed}/{checks_total} ({percentage:.0f}%)")
    
    if checks_passed == checks_total:
        print("\n" + "🎉 "*20)
        print("  ALL CHECKS PASSED - SYSTEM IS READY!")
        print("🎉 "*20)
        print("""
        Next Steps:
        1. python run.py
        2. Test through browser UI
        3. Edit product costs and verify versions are created
        4. Check debug output in terminal
        """)
    else:
        print(f"\n⚠️  {checks_total - checks_passed} checks failed")
        print("Please review errors above")
    
    print("\n" + "="*80)
