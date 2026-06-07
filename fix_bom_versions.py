"""
One-time script to migrate NULL version values in boms table to 'v1'
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import BOM

app = create_app()

with app.app_context():
    # Find all BOMs with NULL or empty version
    null_boms = BOM.query.filter(
        db.or_(BOM.version == None, BOM.version == '')
    ).all()
    
    print(f"Found {len(null_boms)} BOMs with empty/NULL version")
    
    for bom in null_boms:
        bom.version = 'v1'
        print(f"  -> Updated BOM id={bom.id} name='{bom.name}' -> version='v1'")
    
    if null_boms:
        db.session.commit()
        print(f"Committed {len(null_boms)} updates.")
    else:
        print("No BOMs needed updating.")
    
    # Show current state
    all_boms = BOM.query.all()
    print(f"\nCurrent BOM versions:")
    for b in all_boms:
        print(f"  id={b.id}, name='{b.name}', version='{b.version}'")
