#!/usr/bin/env python
"""
Test BOM versioning through Flask test client (simulates browser request)
"""
from app import create_app, db
from app.models import Product, User

app = create_app()
client = app.test_client()

with app.app_context():
    print("\n" + "="*80)
    print("TEST: Edit Product via Flask Test Client (Simulates Browser)")
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
    
    # Login
    with client:
        login_response = client.post('/auth/login', data={
            'username': 'admin',
            'password': 'password'  # Default for testing
        })
        
        print(f"\n" + "-"*80)
        print("LOGIN ATTEMPT")
        print("-"*80)
        print(f"Response status: {login_response.status_code}")
        
        # Try to edit the product
        old_price = product.cost_price
        new_price = old_price + 50
        
        print(f"\n" + "-"*80)
        print("EDITING PRODUCT (via browser form)")
        print("-"*80)
        print(f"Old price: Rs {old_price}")
        print(f"New price: Rs {new_price}")
        
        edit_response = client.post(f'/inventory/product/{product.id}/edit', data={
            'name': product.name,
            'sku': product.sku,
            'description': product.description or '',
            'unit_price': product.unit_price or 0,
            'cost_price': new_price,
            'reorder_level': product.reorder_level or 0,
            'category': product.category or ''
        }, follow_redirects=False)
        
        print(f"\nResponse status: {edit_response.status_code}")
        print(f"Response location: {edit_response.location}")
        
        # Refresh product
        db.session.refresh(product)
        print(f"\n{'='*80}")
        print(f"RESULT:")
        print(f"{'='*80}")
        print(f"Product cost_price: Rs {product.cost_price}")
        print(f"Expected: Rs {new_price}")
        
        if product.cost_price == new_price:
            print(f"\n✓ Product cost was updated!")
        else:
            print(f"\n✗ Product cost was NOT updated!")
        
        # Check BOM version
        if product.bom_items:
            print(f"\nBOM using this product:")
            for item in product.bom_items:
                bom = item.bom
                print(f"  - {bom.name}: {bom.version}")
