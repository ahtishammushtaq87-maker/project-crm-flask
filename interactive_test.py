#!/usr/bin/env python
"""
Interactive test - start the server and ask user to edit a product
"""
import sys
from app import create_app

app = create_app()

print("\n" + "="*80)
print("BOM VERSIONING TEST - INTERACTIVE MODE")
print("="*80)
print("""
This test will start the Flask server so you can manually test BOM versioning.

INSTRUCTIONS:
1. The server will start at http://127.0.0.1:5000
2. Login with admin / password
3. Go to: Inventory → Products
4. Click "Edit" on any product
5. Change the "Cost Price" field to a different value
6. Click Save
7. WATCH THE TERMINAL for debug output:
   - Look for [DEBUG] messages
   - Look for [BOM_VERSION_SERVICE] messages
   - These will show if versioning was triggered

DEBUG OUTPUT SHOULD SHOW:
  [DEBUG] Product X (name) updated
  [DEBUG] Old cost: X.X, New cost: Y.Y
  [DEBUG] Cost changed! Triggering BOM versioning...
  [BOM_VERSION_SERVICE] Found X BOM items
  [BOM_VERSION_SERVICE] ✓ COST MISMATCH DETECTED!

8. After you edit a product, come back to the terminal and press Ctrl+C

""")

input("Press ENTER to start the server...")

print("\nStarting Flask server...")
print("Server will run on http://127.0.0.1:5000")
print("\nTo stop: Press Ctrl+C\n")

# Run the Flask server
app.run(debug=True, use_reloader=False)
