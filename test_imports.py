#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

try:
    from app import create_app, db
    print("✓ App created successfully")
    
    from app.routes import accounting
    print("✓ Accounting routes imported successfully")
    
    from app.models import Expense
    print("✓ Models imported successfully")
    
    print("\n✓ All imports successful!")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
