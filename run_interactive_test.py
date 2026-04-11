#!/usr/bin/env python
"""
Start the Flask app for manual browser testing with extensive debug output
"""
from app import create_app
import logging

# Enable all Flask and SQLAlchemy logging
logging.basicConfig(level=logging.DEBUG)

app = create_app()

print("\n" + "="*80)
print("STARTING FLASK SERVER FOR INTERACTIVE BOM VERSIONING TEST")
print("="*80)
print("""
SERVER: http://127.0.0.1:5000

LOGIN CREDENTIALS:
  Username: admin
  Password: password

TEST STEPS:
1. Login to the application
2. Navigate to: Inventory → Products
3. Click "Edit" on "Test Product"
4. Change the "Cost Price" from Rs 1350.0 to a different value (e.g., Rs 1500.0)
5. Click "Save"
6. Watch the TERMINAL for debug output:
   - You should see [DEBUG] messages from inventory.py
   - You should see [BOM_VERSION_SERVICE] messages from the service
   - Success message in the browser

7. Check the BOM versions:
   - Go to Manufacturing → BOMs
   - Click "car" BOM
   - You should see a new version v5 created

DEBUG OUTPUT SAMPLE (if working):
  [DEBUG] Product 1 (Test Product) updated
  [DEBUG] Old cost: 1350.0, New cost: 1500.0
  [DEBUG] Costs equal? False
  [DEBUG] Cost changed! Triggering BOM versioning...
  [DEBUG] Calling check_and_update_bom_for_cost_changes...
  [BOM_VERSION_SERVICE] check_and_update_bom_for_cost_changes called
  [BOM_VERSION_SERVICE] Product ID: 1, User ID: 2
  [BOM_VERSION_SERVICE] Found 1 BOM items using this product
  ...

Press Ctrl+C in the terminal to stop the server.
""")

input("Press ENTER to start the server...")

print("\nStarting server on http://127.0.0.1:5000...")
print("="*80 + "\n")

app.run(debug=True, use_reloader=False, host='127.0.0.1', port=5000)
