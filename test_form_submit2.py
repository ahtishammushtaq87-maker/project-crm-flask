#!/usr/bin/env python
"""
Test BOM versioning through Flask test client with proper session handling
"""
from app import create_app, db
from app.models import Product, User
from flask import session

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("TEST: Edit Product via Flask Test Client (with proper session)")
    print("="*80)
    
    # Get admin user
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print("✗ No admin user found")
        exit(1)
    
    print(f"\nAdmin: {admin.username} (ID: {admin.id})")
    
    # Get first product
    product = Product.query.first()
    if not product:
        print("✗ No product found")
        exit(1)
    
    print(f"\nProduct: {product.name} (ID: {product.id})")
    print(f"Current cost_price: Rs {product.cost_price}")
    
    # Create test client
    client = app.test_client()
    
    # Use app context and test_request_context to properly login
    with app.test_request_context():
        # Import and use flask_login to properly login
        from flask_login import login_user
        
        # Create a request context with the test client
        response = client.get('/')  # Any route to establish session
        
        print(f"\n" + "-"*80)
        print("SIMULATING BROWSER SESSION")
        print("-"*80)
        
        # Now try editing with test request context
        old_price = product.cost_price
        new_price = old_price + 75
        
        print(f"\nOld price: Rs {old_price}")
        print(f"New price: Rs {new_price}")
        
        # Use session for login simulation
        with client.session_transaction() as sess:
            # Manually set the user ID in session (simulate login)
            sess['user_id'] = admin.id
            sess['_user_id'] = admin.id
        
        # Now make the POST request
        print(f"\n" + "-"*80)
        print("POSTING FORM DATA")
        print("-"*80)
        
        edit_response = client.post(
            f'/inventory/product/{product.id}/edit',
            data={
                'name': product.name,
                'sku': product.sku,
                'description': product.description or '',
                'unit_price': product.unit_price or 0,
                'cost_price': new_price,
                'reorder_level': product.reorder_level or 0,
                'category': product.category or '',
                'is_manufactured': False
            },
            follow_redirects=True
        )
        
        print(f"Response status: {edit_response.status_code}")
        
        # Check if product was updated
        db.session.refresh(product)
        print(f"\n{'='*80}")
        print(f"RESULT:")
        print(f"{'='*80}")
        print(f"Product cost_price: Rs {product.cost_price}")
        print(f"Expected: Rs {new_price}")
        
        if product.cost_price == new_price:
            print(f"\n✓ Product cost was updated successfully!")
            print(f"✓ BOM versioning should have been triggered!")
        else:
            print(f"\n✗ Product cost was NOT updated")
