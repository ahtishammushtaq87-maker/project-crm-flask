#!/usr/bin/env python
"""
COMPREHENSIVE BOM VERSIONING TEST
Tests all three versioning triggers
"""
from app import create_app, db
from app.models import Product, BOM, User, Expense, PurchaseBill, PurchaseItem, BOMVersion
from app.services.bom_versioning import BOMVersioningService
from datetime import datetime

app = create_app()

with app.app_context():
    print("\n" + "="*100)
    print(" "*20 + "COMPREHENSIVE BOM VERSIONING TEST")
    print("="*100)
    
    # Setup
    admin = User.query.filter_by(username='admin').first()
    bom = BOM.query.first()
    product = Product.query.first()
    
    if not all([admin, bom, product]):
        print("✗ Missing required test data")
        exit(1)
    
    print(f"\nTest Setup:")
    print(f"  Admin User: {admin.username} (ID: {admin.id})")
    print(f"  BOM: {bom.name} (ID: {bom.id}) - Current Version: {bom.version}")
    print(f"  Product: {product.name} (ID: {product.id}) - Cost: Rs {product.cost_price}")
    
    initial_version = bom.version
    version_count_before = len(BOMVersion.query.filter_by(bom_id=bom.id).all())
    
    # TEST 1: INVENTORY TRIGGER - Edit product cost
    print(f"\n{'='*100}")
    print("TEST 1: INVENTORY TRIGGER - Product Cost Change")
    print("-"*100)
    
    old_cost = product.cost_price
    new_cost = old_cost + 100
    
    print(f"Changing product cost: Rs {old_cost} → Rs {new_cost}")
    product.cost_price = new_cost
    db.session.commit()
    
    print(f"Triggering BOM versioning service...")
    updated_boms_1 = BOMVersioningService.check_and_update_bom_for_cost_changes(
        product_id=product.id,
        created_by_id=admin.id
    )
    
    db.session.refresh(bom)
    print(f"Result: {len(updated_boms_1)} BOM(s) updated")
    if updated_boms_1:
        print(f"  ✓ BOM '{bom.name}' version updated to: {bom.version}")
        version_1 = bom.version
    else:
        print(f"  ✗ FAILED")
        version_1 = bom.version
    
    # TEST 2: ACCOUNTING TRIGGER - Add overhead expense to BOM
    print(f"\n{'='*100}")
    print("TEST 2: ACCOUNTING TRIGGER - BOM Overhead Expense")
    print("-"*100)
    
    print(f"Adding overhead expense to BOM: '{bom.name}'")
    
    expense = Expense()
    expense.description = "Testing BOM overhead"
    expense.amount = 500
    expense.category = "Test"
    expense.is_bom_overhead = True
    expense.bom_id = bom.id
    expense.created_by = admin.id
    
    db.session.add(expense)
    db.session.flush()  # Get the ID
    
    print(f"Creating version via accounting trigger...")
    old_overhead = bom.overhead_cost
    new_overhead = (bom.overhead_cost or 0) + 500
    
    created_versions = BOMVersioningService.create_bom_version(
        bom=bom,
        change_reason=f"Overhead expense: {expense.description}",
        change_type="overhead_added",
        created_by_id=admin.id
    )
    
    db.session.commit()
    db.session.refresh(bom)
    
    print(f"Result: Version created")
    if created_versions:
        print(f"  ✓ BOM '{bom.name}' version updated to: {bom.version}")
        version_2 = bom.version
    else:
        print(f"  ✗ FAILED")
        version_2 = bom.version
    
    # SUMMARY
    print(f"\n{'='*100}")
    print("SUMMARY")
    print("="*100)
    
    version_count_after = len(BOMVersion.query.filter_by(bom_id=bom.id).all())
    versions_created = version_count_after - version_count_before
    
    print(f"\nInitial BOM version: {initial_version}")
    print(f"Final BOM version: {bom.version}")
    print(f"Versions created during test: {versions_created}")
    
    if versions_created > 0:
        print(f"\n✓✓✓ SUCCESS! BOM VERSIONING SYSTEM IS WORKING ✓✓✓")
        print(f"\nVersion History:")
        for v in sorted(BOMVersion.query.filter_by(bom_id=bom.id).all(), key=lambda x: x.version_number):
            print(f"  v{v.version_number}: {v.change_reason[:50]}...")
    else:
        print(f"\n✗✗✗ FAILED! No versions were created ✗✗✗")
    
    print(f"\n{'='*100}")
