#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

try:
    from app import create_app
    app = create_app()
    
    # Check if bulk approval endpoint is registered in the routing rules
    found = False
    for rule in app.url_map.iter_rules():
        if 'universal-bulk-approval' in rule.rule:
            print(f"✓ Found registered endpoint: {rule.endpoint} -> {rule.rule} (methods: {sorted(list(rule.methods))})")
            found = True
            break
            
    if not found:
        print("✗ Could not find universal-bulk-approval endpoint in routing rules!")
        sys.exit(1)
        
    print("\n✓ Verification successful!")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
