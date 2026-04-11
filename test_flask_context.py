#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test BOM versioning within Flask request context (simulates actual browser request)
"""
from app import create_app, db
from app.models import Product, User
import traceback

app = create_app()

print("\n" + "="*80)
print("TEST: BOM Versioning in Flask Request Context")
print("="*80)

# Get test data BEFORE entering request context
admin = None
product = None

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    product = Product.query.first()

if not admin or not product:
    print("ERROR: Missing test data")
    exit(1)

print(f"\nTest data loaded: Admin={admin.username}, Product={product.name}")

# Now test within a request context (like when Flask processes a request)
with app.test_request_context():
    print("\n" + "-"*80)
    print("Inside Flask request context...")
    print("-"*80)
    
    try:
        # Import Flask-Login utilities
        from flask_login import current_user
        print(f"\n[1] Imported current_user: {current_user}")
        print(f"[2] current_user.is_authenticated: {current_user.is_authenticated}")
        
        # When outside a request with user context, current_user is AnonymousUserMixin
        # That's the problem! We need to manually set the user or use a different approach
        
        # Try calling the route code
        from app.services.bom_versioning import BOMVersioningService
        
        old_cost = product.cost_price
        new_cost = old_cost + 50
        
        print(f"\n[3] Changing product cost: {old_cost} -> {new_cost}")
        product.cost_price = new_cost
        db.session.commit()
        
        print(f"[4] Calling BOMVersioningService...")
        print(f"    with created_by_id={admin.id} (passed explicitly)")
        
        updated_boms = BOMVersioningService.check_and_update_bom_for_cost_changes(
            product_id=product.id,
            created_by_id=admin.id
        )
        
        print(f"\n✅ SUCCESS! Updated {len(updated_boms)} BOM(s)")
        
    except NameError as e:
        print(f"\n❌ NameError: {e}")
        traceback.print_exc()
        
        print(f"\n" + "="*80)
        print("ISSUE IDENTIFIED:")
        print("="*80)
        print(f"""
The problem is that in a Flask request context without a logged-in user,
current_user is an AnonymousUserMixin object and doesn't have an .id attribute.

However, looking at the code in inventory.py:
  created_by_id=current_user.id

This should work ONLY when the user is logged in via @login_required decorator.

The error message shows up because:
1. The try-except in inventory.py line 167 catches the error
2. It displays: "Product updated, but error updating BOM versions: {error}"

This means the error IS happening, but it's being caught and shown to user.

SOLUTION: The issue might be that current_user is not properly available
in the Flask context. We need to check if this is a Flask-Login configuration issue.
        """)
        
    except Exception as e:
        print(f"\n⚠️  Other error: {type(e).__name__}: {e}")
        traceback.print_exc()

print("\n" + "="*80)
