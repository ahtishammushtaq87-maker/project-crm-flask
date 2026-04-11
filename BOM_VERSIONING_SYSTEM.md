# BOM Version Control System

## Overview

A complete Bill of Materials (BOM) version control system that automatically tracks and creates new BOM versions when:
1. **Component costs increase** - Product cost_price changes
2. **Overhead expenses are added** - Manufacturing overhead changes
3. **Shipping costs added** - Per-product shipping from purchase bills

The system maintains a complete audit trail with version history, cost comparisons, and automatic version numbering (v1, v2, v3, etc).

---

## Features Implemented

### 1. **Version Numbering**
- BOMs now have versions: v1, v2, v3, etc.
- Automatic version increment when changes detected
- Each version is immutable snapshot of BOM at that time

### 2. **Per-Product Shipping Tracking**
- **New Field:** `PurchaseItem.shipping_charge` - Total shipping for item
- **New Property:** `PurchaseItem.per_unit_shipping` - Shipping per unit
- Automatically allocates purchase shipping to BOM components
- Included in BOM total cost calculations

### 3. **Automatic Version Creation**
Triggered by:
- ✅ Component product cost price increases
- ✅ Overhead expense amount changes
- ✅ Shipping cost allocated to items
- ✅ Manual version request

### 4. **Version History Tracking**
Each version records:
- Version number (v1, v2, etc.)
- Labor cost at that time
- Overhead cost at that time
- Total BOM cost
- Change reason (e.g., "Component price increased")
- Change type (component_cost, overhead_added, etc.)
- Previous version reference
- Timestamp and user who made change
- Snapshot of all components and their costs

### 5. **Version Comparison**
Compare two BOM versions:
- Side-by-side cost comparison
- Component-by-component differences
- Percentage change calculation
- Identify what caused the change

---

## Database Schema

### New Tables

**bom_versions**
```sql
CREATE TABLE bom_versions (
    id INTEGER PRIMARY KEY,
    bom_id INTEGER,              -- Which BOM
    version_number VARCHAR(10),  -- v1, v2, v3
    labor_cost FLOAT,           -- Cost at this version
    overhead_cost FLOAT,        -- Cost at this version
    total_cost FLOAT,           -- Total at this version
    change_reason VARCHAR(200), -- Why changed
    change_type VARCHAR(50),    -- component_cost, overhead_added
    previous_version VARCHAR(10), -- v1, v2, etc
    created_at DATETIME,        -- When created
    created_by INTEGER          -- User ID
)
```

**bom_version_items**
```sql
CREATE TABLE bom_version_items (
    id INTEGER PRIMARY KEY,
    version_id INTEGER,         -- Which version
    component_id INTEGER,       -- Which product
    quantity FLOAT,             -- Qty at this version
    unit_cost FLOAT,            -- Cost per unit then
    shipping_per_unit FLOAT,    -- Shipping per unit then
    total_cost FLOAT            -- Total for this item
)
```

### Modified Tables

**purchase_items** - Added:
- `shipping_charge FLOAT` - Total shipping for this item

**bom_items** - Modified:
- `cost` → `unit_cost` - Cost per unit
- Added `shipping_per_unit FLOAT` - Shipping per unit
- Added `total_cost FLOAT` - Complete item cost
- Added `cost_price_history_id` - Track which cost price version

**boms** - Added:
- `version VARCHAR(10)` - Current version (v1, v2)
- `is_active BOOLEAN` - Only latest is active

---

## Usage

### Creating a BOM (with v1)
```
1. Manufacturing → Add BOM
2. Select finished product
3. Add components with quantities
4. Set labor cost and overhead
5. Save

Result:
- BOM created with version='v1'
- BOMVersion entry created for v1
- BOMVersionItem entries created (snapshot)
```

### When Component Cost Increases
```
Example:
- Widget component: Old cost Rs 50, new cost Rs 55
- System detects change automatically
- Creates new BOM version v2 with:
  * Old components and costs (from v1)
  * Updated component at new cost
  * New total_cost
  * change_reason: "Component Widget cost changed from Rs 50 to Rs 55"
  * change_type: "component_cost"
```

### When Overhead Expense Added
```
Example:
- Manufacturing overhead: Rs 100 added
- System creates new BOM version v2 with:
  * Same components as v1
  * Updated overhead_cost
  * New total_cost
  * change_reason: "Overhead cost changed from Rs 100 to Rs 200"
  * change_type: "overhead_added"
```

### Viewing Version History
```
1. Manufacturing → BOMs
2. Click on BOM
3. New button: "Version History"
4. Shows:
   - Current version and cost
   - Table of all versions v1, v2, v3...
   - Each row shows:
     * Version number
     * Total cost
     * Change reason
     * Date created
     * Changed by user
```

### Comparing Versions
```
1. Click "Compare Versions" on version history page
2. Select two versions (e.g., v1 and v3)
3. View comparison:
   - Side-by-side costs
   - Component differences
   - Percentage change
   - What triggered each change
```

---

## Service API

### BOMVersioningService

```python
# Create new version
BOMVersioningService.create_bom_version(
    bom=bom_object,
    change_reason="Component price increase",
    change_type="component_cost",
    created_by_id=user_id
)

# Get version history (most recent first)
versions = BOMVersioningService.get_bom_version_history(bom_id)

# Check for cost changes and auto-update BOM
updated_boms = BOMVersioningService.check_and_update_bom_for_cost_changes(
    product_id=product_id,
    created_by_id=user_id
)

# Check and update overhead
version = BOMVersioningService.check_and_update_bom_for_overhead_changes(
    bom_id=bom_id,
    new_overhead=new_value,
    old_overhead=old_value,
    created_by_id=user_id
)

# Compare two versions
comparison = BOMVersioningService.compare_bom_versions(
    version1_id=v1.id,
    version2_id=v2.id
)

# Allocate shipping from purchase to BOM items
BOMVersioningService.allocate_purchase_shipping_to_bom(
    purchase_item_id=purchase_item_id
)
```

---

## REST API Endpoints

### Get BOM Versions
```
GET /manufacturing/api/bom/{bom_id}/versions

Response:
{
  "bom_id": 1,
  "bom_name": "Product Name",
  "current_version": "v2",
  "current_cost": 1500.0,
  "versions": [
    {
      "id": 2,
      "version_number": "v2",
      "total_cost": 1500.0,
      "change_reason": "Component price increased",
      "change_type": "component_cost",
      "created_at": "08-04-2026 14:30",
      "created_by": "admin"
    }
  ]
}
```

### Compare Versions
```
GET /manufacturing/api/bom/versions/{v1_id}/compare/{v2_id}

Response:
{
  "version1": { "version": "v1", "total_cost": 1000.0, ... },
  "version2": { "version": "v2", "total_cost": 1500.0, ... },
  "cost_difference": 500.0,
  "percentage_change": 50.0
}
```

### Check for Updates
```
POST /manufacturing/api/bom/{bom_id}/check-updates

Response:
{
  "bom_id": 1,
  "current_version": "v2",
  "needs_update": true,
  "changed_components": [
    {
      "name": "Widget",
      "old_cost": 50.0,
      "new_cost": 55.0,
      "difference": 5.0
    }
  ]
}
```

### View Version History
```
GET /manufacturing/bom/{bom_id}/versions

Displays:
- BOM details
- Current version and cost
- Table of all versions with history
- Compare and export buttons
```

---

## Example Workflow

### Scenario: Component Price Changes Over Time

**Day 1: Create BOM**
```
Product: Finished Widget
Components:
- Component A: 10 units @ Rs 50 each = Rs 500
- Component B: 5 units @ Rs 100 each = Rs 500
Labor: Rs 200
Overhead: Rs 200
Total: Rs 1400

Result: BOM v1 created with total_cost = 1400
```

**Day 15: Component A Price Increases to Rs 60**
```
System detects:
- Component A cost changed from Rs 50 to Rs 60
- Component A in BOM v1: 10 units @ Rs 50 = Rs 500
- Component A now: 10 units @ Rs 60 = Rs 600
- Difference: Rs 100

System creates:
- BOM v2 with:
  * Component A: 10 units @ Rs 60 = Rs 600 (UPDATED)
  * Component B: 5 units @ Rs 100 = Rs 500 (same)
  * Labor: Rs 200 (same)
  * Overhead: Rs 200 (same)
  * Total: Rs 1500 (INCREASED by Rs 100)
  * change_reason: "Component A cost changed from Rs 50 to Rs 60"
  * change_type: "component_cost"
```

**Day 20: Overhead Increased to Rs 300**
```
System creates:
- BOM v3 with:
  * All components same as v2
  * Overhead: Rs 300 (UPDATED)
  * Total: Rs 1600 (INCREASED by Rs 100)
  * change_reason: "Overhead cost changed from Rs 200 to Rs 300"
  * change_type: "overhead_added"
```

**Day 25: View History**
```
Clicking "Version History" shows:
┌─────────────────────────────────────────────┐
│ BOM: Finished Widget (Current: v3)          │
│ Current Cost: Rs 1600                       │
├─────────────────────────────────────────────┤
│ Version │ Cost    │ Reason          │ Date  │
│─────────┼─────────┼─────────────────┼───────│
│ v3      │ 1600.00 │ Overhead added  │ 20-04 │
│ v2      │ 1500.00 │ Component A ↑   │ 15-04 │
│ v1      │ 1400.00 │ Initial         │ 01-04 │
└─────────────────────────────────────────────┘

Total increase: Rs 200 (14.3%)
```

---

## Shipping Cost Integration

### How Shipping Works

**During Purchase Bill Creation**
```
Purchase Bill Item:
- Product: Component A
- Quantity: 100 units
- Unit Price: Rs 50
- Total: Rs 5000
- Shipping Charge (NEW): Rs 500  ← Per-item shipping

Per-unit Shipping = 500 / 100 = Rs 5 per unit
```

**In BOM Component Cost**
```
BOM Item for Component A:
- Unit Cost: Rs 50
- Shipping per Unit: Rs 5  ← From last purchase
- Total per Unit: Rs 55
- Qty in BOM: 10 units
- Total Cost: 10 * 55 = Rs 550

When showing BOM cost breakdown:
├─ Raw component cost: Rs 500
└─ Shipping allocation: Rs 50
   Total: Rs 550
```

---

## Benefits

✅ **Complete Cost Tracking** - See all BOM cost changes with reasons
✅ **Automatic Versioning** - New version created automatically when costs change
✅ **Audit Trail** - Full history with dates, users, reasons
✅ **Easy Comparison** - Compare costs between any two versions
✅ **Shipping Tracking** - Include purchase shipping in product costs
✅ **Immutable Records** - Each version is snapshot (cannot be modified)
✅ **Decision Support** - Know exactly when and why costs changed

---

## Files Modified/Created

### Created
- `app/services/bom_versioning.py` - BOM versioning service
- `migrate_bom_versioning.py` - Database migration
- Documentation files

### Modified
- `app/models.py`:
  - Enhanced BOM model
  - Enhanced BOMItem model
  - Added BOMVersion model
  - Added BOMVersionItem model
  - Enhanced PurchaseItem model

- `app/routes/manufacturing.py`:
  - Updated add_bom() for versioning
  - Added versioning endpoints (API)
  - Added view_bom_versions() route

---

## Database Migration Status

✅ `shipping_charge` added to purchase_items
✅ `bom_versions` table created
✅ `bom_version_items` table created
✅ `bom_items` modified with new columns
✅ `boms` modified with version tracking
✅ 4 indices created for performance

---

## Testing Scenarios

1. **Create BOM v1** - Check initial version created
2. **Increase component cost** - Check v2 auto-created
3. **Add overhead** - Check v3 auto-created
4. **View history** - Check all versions displayed
5. **Compare versions** - Check cost differences shown
6. **Add shipping** - Check shipping allocated to BOM items
7. **Check for updates** - API detects cost changes

---

## Future Enhancements

- 🔄 Automatic reversion to old version if cost drops
- 📊 Cost trend analysis across versions
- 📧 Alerts on significant cost increases
- 📉 Profitability impact analysis
- 🔗 Link to purchase bills that caused changes
- 📄 Version comparison reports/PDF export

---

**Implementation Date:** April 8, 2026
**Status:** ✅ COMPLETE
**Database Status:** ✅ MIGRATED
**App Status:** ✅ VERIFIED
