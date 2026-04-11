#!/usr/bin/env python
"""
Direct database test - bypass Flask completely
"""
from app import create_app, db
from app.models import Product, BOM, BOMItem
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("DIRECT DATABASE TEST")
    print("="*80)
    
    # Check all BOMs with their items
    boms = BOM.query.all()
    print(f"\nTotal BOMs in database: {len(boms)}")
    
    for bom in boms:
        print(f"\n{'='*80}")
        print(f"BOM: {bom.name} (ID: {bom.id})")
        print(f"Current Version: {bom.version}")
        print(f"Total Cost: Rs {bom.total_cost}")
        print(f"Items in BOM:")
        
        for item in bom.items:
            product = item.component
            print(f"\n  - Component: {product.name} (ID: {product.id})")
            print(f"    Product cost_price: Rs {product.cost_price}")
            print(f"    BOM item unit_cost: Rs {item.unit_cost}")
            print(f"    BOM item total_cost: Rs {item.total_cost}")
            
            # Check if mismatch exists
            if product.cost_price != item.unit_cost:
                print(f"    ⚠️ MISMATCH DETECTED!")
                print(f"       Should trigger version update from {bom.version} to v{int(bom.version[1:])+1}")
    
    # Show BOM versions
    print(f"\n\n{'='*80}")
    print("BOM VERSIONS IN DATABASE")
    print("="*80)
    
    bom_versions = db.session.query(text("id, bom_id, version_number, change_reason FROM bom_versions")).all()
    print(f"Total BOM versions: {len(bom_versions)}")
    
    for version in bom_versions:
        print(f"\nVersion: v{version[2]} (ID: {version[0]})")
        print(f"  BOM ID: {version[1]}")
        print(f"  Reason: {version[3]}")
