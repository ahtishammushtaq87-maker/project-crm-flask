#!/usr/bin/env python
"""
QUICK START - BOM VERSIONING SYSTEM TESTING

Run this to verify the BOM versioning system is working before starting the app.
"""
from app import create_app, db
from app.models import Product, BOM, User, BOMVersion
from app.services.bom_versioning import BOMVersioningService

app = create_app()

with app.app_context():
    print("\n" + "█"*80)
    print("  BOM VERSIONING SYSTEM - QUICK START VERIFICATION")
    print("█"*80 + "\n")
    
    # Check database
    bom_count = len(BOM.query.all())
    version_count = len(BOMVersion.query.all())
    product_count = len(Product.query.all())
    
    print(f"Database Status:")
    print(f"  ✓ BOMs in database: {bom_count}")
    print(f"  ✓ BOM versions in database: {version_count}")
    print(f"  ✓ Products in database: {product_count}")
    
    if bom_count == 0 or product_count == 0:
        print(f"\n⚠️  WARNING: Not enough test data. Initialize database first.")
        exit(1)
    
    # Get test data
    bom = BOM.query.first()
    product = Product.query.first()
    admin = User.query.filter_by(username='admin').first()
    
    print(f"\nTest Data:")
    print(f"  ✓ Test BOM: {bom.name} (Current version: {bom.version})")
    print(f"  ✓ Test Product: {product.name} (Cost: Rs {product.cost_price})")
    print(f"  ✓ Admin User: {admin.username if admin else 'NOT FOUND'}")
    
    if not admin:
        print(f"\n⚠️  WARNING: Admin user not found. Create user first.")
        exit(1)
    
    print(f"\n" + "="*80)
    print("Testing Versioning Trigger...")
    print("="*80 + "\n")
    
    # Test the trigger
    old_cost = product.cost_price
    new_cost = old_cost + 100
    version_before = bom.version
    
    print(f"Scenario:")
    print(f"  Product cost: Rs {old_cost} → Rs {new_cost}")
    print(f"  BOM version before: {version_before}")
    print()
    
    # Simulate product edit
    product.cost_price = new_cost
    db.session.commit()
    
    # Trigger versioning
    updated_boms = BOMVersioningService.check_and_update_bom_for_cost_changes(
        product_id=product.id,
        created_by_id=admin.id
    )
    
    db.session.refresh(bom)
    version_after = bom.version
    
    print(f"Result:")
    print(f"  ✓ BOMs updated: {len(updated_boms)}")
    print(f"  ✓ BOM version after: {version_after}")
    
    if version_after != version_before:
        print(f"\n{'✅'*40}")
        print(f"  SUCCESS! BOM VERSIONING IS WORKING")
        print(f"  Version successfully incremented: {version_before} → {version_after}")
        print(f"{'✅'*40}")
    else:
        print(f"\n{'❌'*40}")
        print(f"  FAILED! Version did not change")
        print(f"{'❌'*40}")
    
    print(f"\n" + "="*80)
    print("Next Steps:")
    print("="*80)
    print("""
1. START THE APP:
   python run.py

2. LOGIN:
   - Username: admin
   - Password: password

3. TEST IN BROWSER:
   - Go to: Inventory → Products
   - Click "Edit" on any product
   - Change the Cost Price
   - Click Save
   - Watch the terminal for [DEBUG] messages

4. VERIFY VERSIONING:
   - Go to: Manufacturing → BOMs
   - Click on a BOM name
   - Check that new version appears in history

5. CHECK DEBUG OUTPUT:
   - Look for [DEBUG] messages in terminal
   - Look for [BOM_VERSION_SERVICE] messages
   - Both confirm versioning was triggered

Questions? Check: BOM_VERSIONING_TEST_REPORT.md
    """)
