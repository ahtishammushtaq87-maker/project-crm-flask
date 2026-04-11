#!/usr/bin/env python
"""
Check BOM version history
"""
from app import create_app, db
from app.models import BOMVersion, BOM

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("BOM VERSION HISTORY")
    print("="*80)
    
    bom = BOM.query.first()
    if not bom:
        print("No BOM found")
        exit(1)
    
    print(f"\nBOM: {bom.name} (ID: {bom.id})")
    print(f"Current Version: {bom.version}")
    
    versions = BOMVersion.query.filter_by(bom_id=bom.id).order_by(BOMVersion.version_number).all()
    
    print(f"\nTotal versions: {len(versions)}")
    print(f"\n{'='*80}")
    
    for version in versions:
        print(f"\nv{version.version_number}: (ID: {version.id})")
        print(f"  Total Cost: Rs {version.total_cost}")
        print(f"  Change Reason: {version.change_reason}")
        print(f"  Change Type: {version.change_type}")
        print(f"  Created By: User ID {version.created_by}")
        
        # Show items in this version
        print(f"  Items:")
        for item in version.items:
            print(f"    - {item.component.name}: Rs {item.unit_cost}")
