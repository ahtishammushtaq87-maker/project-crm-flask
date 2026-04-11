#!/usr/bin/env python
"""
BOM Versioning Triggers - Complete Documentation
Shows all scenarios where new BOM versions are automatically created
"""

print("""
═══════════════════════════════════════════════════════════════════════════════
                    BOM VERSIONING - AUTOMATIC TRIGGERS
═══════════════════════════════════════════════════════════════════════════════

TRIGGER 1: Component Cost Increase (From Purchase Bill)
───────────────────────────────────────────────────────
Location: app/routes/purchase.py → create_bill()
When: A purchase bill is created with a component at a different price
Action: 
  1. System detects price differs from product.cost_price
  2. Creates CostPriceHistory entry
  3. Updates product.cost_price to new price
  4. AFTER saving bill, calls BOMVersioningService.check_and_update_bom_for_cost_changes()
  5. For each BOM using this product as component:
     - If BOM item's unit_cost != new product cost_price
     - Automatically creates NEW BOM VERSION (v1→v2, v2→v3, etc)
     - Version snapshot includes all items at that time
     - change_reason: "Component 'ProductName' cost changed from Rs X to Rs Y"
     - change_type: 'component_cost'

Example Workflow:
  1. BOM v1 created with Widget Component at Rs 100
  2. Purchase bill created: Widget Component bought at Rs 120 (new price)
  3. Product.cost_price updated to Rs 120
  4. BOMVersioningService detects cost mismatch
  5. ✓ BOM v2 automatically created with new component cost
  6. Version history now shows:
     - v2: Component 120 | Component cost changed | Date
     - v1: Component 100 | Initial | Date

═══════════════════════════════════════════════════════════════════════════════

TRIGGER 2: Component Cost Increase (From Inventory Edit)
──────────────────────────────────────────────────────────
Location: app/routes/inventory.py → edit_product()
When: A product's cost_price is manually changed in inventory
Action:
  1. User edits product and changes cost_price
  2. System stores old_cost before update
  3. Saves product with new cost_price
  4. AFTER saving, checks if old_cost != new cost_price
  5. If changed, calls BOMVersioningService.check_and_update_bom_for_cost_changes()
  6. For each BOM using this product:
     - Automatically creates NEW BOM VERSION
     - Updates BOM item.unit_cost to new price
     - Creates version snapshot
     - change_reason: "Component 'ProductName' cost changed..."

Example Workflow:
  1. BOM v1 created with Part A at Rs 50
  2. Inventory → Edit Part A → Change cost_price to Rs 75
  3. User clicks Save
  4. ✓ BOM v2 automatically created
  5. Version shows:
     - v2: Part A 75 | Component cost changed | Date
     - v1: Part A 50 | Initial | Date

═══════════════════════════════════════════════════════════════════════════════

TRIGGER 3: BOM Overhead Expense Added (From Accounting)
─────────────────────────────────────────────────────────
Location: app/routes/accounting.py → add_expense() and edit_expense()
When: An expense is marked as "BOM Overhead Expense" and linked to a BOM or product
Action:
  1. User adds expense and checks "BOM Overhead Expense"
  2. Selects either:
     a. Finished Product → System finds its BOM
     b. BOM directly → Uses selected BOM
  3. Expense is saved
  4. AFTER saving, system checks if BOM overhead
  5. Calls BOMVersioningService.create_bom_version()
  6. Automatically creates NEW BOM VERSION
  7. Version snapshot captures current state
  8. change_reason: "Overhead expense added: [ExpenseDescription]"
  9. change_type: 'overhead_added'

Example Workflow:
  1. BOM "Widget Manufacturing" v1 created with overhead Rs 200
  2. Add Expense: "Factory Rent" (April) Rs 300, mark as "BOM Overhead"
  3. Select BOM: "Widget Manufacturing"
  4. Click Save
  5. ✓ BOM v2 automatically created
  6. Version shows:
     - v2: Overhead 300 | Overhead expense added | Date
     - v1: Overhead 200 | Initial | Date

═══════════════════════════════════════════════════════════════════════════════

KEY FEATURES OF AUTOMATIC VERSIONING:
────────────────────────────────────────

✓ Version Numbers: v1 → v2 → v3 → v4 (auto-incremented)
✓ Immutable Snapshots: Each version captures complete BOM state at that time
✓ Change Tracking: Every version records why it was created
✓ Component Snapshots: All items frozen with their unit_cost at that version
✓ Automatic Comparison: View differences between v1 and v2 via API
✓ User Attribution: System records which user triggered the change
✓ Cost History: Full audit trail from v1 to latest version

═══════════════════════════════════════════════════════════════════════════════

API ENDPOINTS TO VIEW VERSIONS:
──────────────────────────────────

1. GET /manufacturing/api/bom/{bom_id}/versions
   Returns: All versions of a BOM as JSON array

2. GET /manufacturing/api/bom/versions/{v1_id}/compare/{v2_id}
   Returns: Side-by-side comparison of two versions

3. POST /manufacturing/api/bom/{bom_id}/check-updates
   Returns: Detects if BOM needs new version due to cost changes

4. GET /manufacturing/bom/{bom_id}/versions
   Returns: HTML page showing version history and comparison

═══════════════════════════════════════════════════════════════════════════════

DATABASE STRUCTURE:
────────────────────

boms table:
  - id, name, product_id
  - version (current: 'v1', 'v2', 'v3')
  - is_active (True for latest, False for older versions)
  - labor_cost, overhead_cost, total_cost
  - created_at, updated_at

bom_versions table:
  - id, bom_id, version_number ('v1', 'v2', etc)
  - labor_cost, overhead_cost, total_cost (snapshot values)
  - change_reason, change_type, previous_version
  - created_at, created_by (user_id)

bom_version_items table:
  - version_id, component_id
  - quantity, unit_cost, shipping_per_unit, total_cost
  - (Complete snapshot of components for that version)

═══════════════════════════════════════════════════════════════════════════════

EXAMPLE COMPLETE LIFECYCLE:
─────────────────────────────

Date: 01-Apr-2026
Action: Create BOM "Widget Manufacturing"
  - Component: Widget Screw Rs 10, Qty 100
  - Labor: Rs 500
  - Overhead: Rs 200
  - Total: Rs 1700
Result: BOM v1 created ✓

Date: 05-Apr-2026
Action: Purchase bill with Widget Screw at Rs 12 (was Rs 10)
Triggers: BOMVersioningService.check_and_update_bom_for_cost_changes()
Result: BOM v2 auto-created ✓
  - Component: Widget Screw Rs 12, Qty 100
  - Labor: Rs 500
  - Overhead: Rs 200
  - Total: Rs 1800
  - Reason: "Component cost changed from Rs 10 to Rs 12"

Date: 10-Apr-2026
Action: Add Expense "Factory Rent" Rs 300 → Mark as BOM Overhead
Triggers: BOMVersioningService.create_bom_version()
Result: BOM v3 auto-created ✓
  - Component: Widget Screw Rs 12, Qty 100
  - Labor: Rs 500
  - Overhead: Rs 500 (200 + 300 new expense)
  - Total: Rs 2000
  - Reason: "Overhead expense added: Factory Rent"

Date: 15-Apr-2026
Action: Edit Widget Screw cost in inventory from Rs 12 to Rs 15
Triggers: BOMVersioningService.check_and_update_bom_for_cost_changes()
Result: BOM v4 auto-created ✓
  - Component: Widget Screw Rs 15, Qty 100
  - Labor: Rs 500
  - Overhead: Rs 500
  - Total: Rs 2000
  - Reason: "Component cost changed from Rs 12 to Rs 15"

Final Version History:
  v4 (Current): Rs 2000 | Component cost changed | 15-Apr | Admin
  v3: Rs 2000 | Overhead expense added | 10-Apr | Admin
  v2: Rs 1800 | Component cost changed | 05-Apr | Admin
  v1 (Original): Rs 1700 | Initial | 01-Apr | Admin

═══════════════════════════════════════════════════════════════════════════════

STATUS: ✓ COMPLETE
- All triggers implemented
- All routes updated
- All versioning logic working
- All models and database schema in place
- Ready for production use

═══════════════════════════════════════════════════════════════════════════════
""")
