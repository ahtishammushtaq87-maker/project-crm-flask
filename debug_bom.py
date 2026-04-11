#!/usr/bin/env python
"""
Debug BOM Versioning - Find what's preventing version creation
"""
from app import create_app, db
from app.models import Product, BOM, BOMItem, BOMVersion, User, Expense
from datetime import datetime

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("DEBUG: BOM VERSIONING SYSTEM")
    print("="*80)
    
    # 1. Check all products
    print("\n1. PRODUCTS IN DATABASE:")
    products = Product.query.all()
    print(f"Total products: {len(products)}")
    for prod in products[:5]:
        print(f"  ID {prod.id}: {prod.name} | Cost: Rs {prod.cost_price} | SKU: {prod.sku}")
    
    # 2. Check all BOMs
    print("\n2. BOMs IN DATABASE:")
    boms = BOM.query.all()
    print(f"Total BOMs: {len(boms)}")
    for bom in boms:
        print(f"  ID {bom.id}: '{bom.name}' (Product: {bom.product.name if bom.product else 'N/A'})")
        print(f"    Version: {bom.version} | Is Active: {bom.is_active}")
        print(f"    Items: {len(bom.items)}")
        for item in bom.items:
            print(f"      - Component: {item.component.name} (ID {item.component_id})")
            print(f"        Unit Cost: Rs {item.unit_cost} | Qty: {item.quantity}")
    
    # 3. Check BOM versions
    print("\n3. BOM VERSIONS:")
    versions = BOMVersion.query.all()
    print(f"Total versions: {len(versions)}")
    for v in versions:
        print(f"  {v.version_number} (ID {v.id}): BOM {v.bom_id} | Total: Rs {v.total_cost}")
        print(f"    Reason: {v.change_reason}")
    
    # 4. Check if there are any expenses
    print("\n4. EXPENSES:")
    expenses = Expense.query.all()
    print(f"Total expenses: {len(expenses)}")
    for exp in expenses[-3:]:
        print(f"  ID {exp.id}: {exp.description}")
        print(f"    BOM ID: {exp.bom_id} | Product ID: {exp.product_id}")
        print(f"    Is BOM Overhead: {exp.is_bom_overhead}")
    
    # 5. Try to manually find BOMs for a component
    print("\n5. TEST: Find BOMs using a component")
    if products:
        test_product = products[0]
        print(f"\nTesting with product: {test_product.name} (ID: {test_product.id})")
        
        # Find BOM items using this product as component
        bom_items = BOMItem.query.filter_by(component_id=test_product.id).all()
        print(f"BOM items using this component: {len(bom_items)}")
        for item in bom_items:
            print(f"  - In BOM {item.bom_id}: {item.bom.name if item.bom else 'BOM NOT FOUND'}")
    
    # 6. Check relationship integrity
    print("\n6. RELATIONSHIP INTEGRITY CHECK:")
    for bom in boms:
        print(f"\nBOM {bom.id}: {bom.name}")
        print(f"  - Product: {bom.product.name if bom.product else '❌ NO PRODUCT'}")
        print(f"  - Items: {len(bom.items)}")
        for item in bom.items:
            comp = item.component
            if comp:
                print(f"    ✓ Component {item.component_id}: {comp.name}")
            else:
                print(f"    ❌ Component {item.component_id}: NOT FOUND")
    
    # 7. Manual test: Simulate what should happen when cost changes
    print("\n" + "="*80)
    print("7. MANUAL TEST: Simulate cost change")
    print("="*80)
    
    if boms and boms[0].items:
        test_bom = boms[0]
        test_item = test_bom.items[0]
        component = test_item.component
        
        print(f"\nTest BOM: {test_bom.name} (v{test_bom.version})")
        print(f"Test Component: {component.name}")
        print(f"Component current cost: Rs {component.cost_price}")
        print(f"BOM item unit_cost: Rs {test_item.unit_cost}")
        
        # Check if they differ
        if component.cost_price != test_item.unit_cost:
            print(f"\n✓ DIFFERENCE FOUND!")
            print(f"  Product cost ({component.cost_price}) ≠ BOM unit_cost ({test_item.unit_cost})")
            print(f"  This SHOULD trigger version creation!")
        else:
            print(f"\n❌ NO DIFFERENCE")
            print(f"  Costs match: Rs {component.cost_price}")
            print(f"  Need to change one to trigger versioning")
    
    print("\n" + "="*80)
