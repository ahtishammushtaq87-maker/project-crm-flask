# Cost Price History Tracking System

## Overview
This system tracks cost price changes for products when new purchases are received at different prices. It allows you to maintain inventory with items purchased at previous prices while tracking remaining quantities at old prices.

## Features Implemented

### 1. Cost Price History Model (`CostPriceHistory`)
**Location:** `app/models.py` (added new model)

**Fields:**
- `product_id` - Reference to product
- `purchase_bill_id` - Reference to purchase bill where price changed
- `old_price` - Previous cost price (nullable for first entry)
- `new_price` - New cost price
- `quantity_at_old_price` - Quantity available at old price when change occurred
- `used_quantity` - Quantity already consumed/used at old price
- `change_date` - When the price changed
- `reason` - Description of change
- `is_active` - Whether old price stock is still active
- `created_by` - User who made the change

**Property:** `remaining_at_old_price` - Calculates remaining qty = quantity_at_old_price - used_quantity

### 2. Database Migration
**File:** `migrate_cost_price_history.py`

Creates `cost_price_history` table with proper indices:
- Index on `product_id` - Find history by product
- Index on `purchase_bill_id` - Find history by bill
- Index on `change_date` - Sort by date

**Status:** ✅ Executed successfully

### 3. Purchase Bill Creation Enhancement
**Location:** `app/routes/purchase.py` (updated `create_bill` route)

**Logic:**
When a bill item is created:
1. Check if item's price differs from product's current cost_price
2. If different:
   - Create `CostPriceHistory` entry recording:
     - Old price (previous cost_price)
     - New price (item's price)
     - Quantity at old price = total quantity - new items
   - Update product's cost_price to new price
3. Creates audit trail of all price changes

**Example Flow:**
```
Product: Widget
- Current stock: 100 units at Rs 50 each
- Purchase bill adds 50 units at Rs 55 each

Result:
- Product quantity: 150 units
- CostPriceHistory entry created:
  * old_price: 50
  * new_price: 55
  * quantity_at_old_price: 100 (remaining old stock)
  * remaining_at_old_price: 100
- Product cost_price updated to 55
```

### 4. Bill Creation Form Enhancement
**Location:** `app/templates/purchase/create_bill.html`

**Changes:**
1. Added new table columns:
   - "Current Cost" - Shows existing cost price (read-only)
   - "New Cost" - Input field for new cost price
   
2. Visual indicators:
   - Display current cost price in each row
   - Auto-fill new cost with current cost
   - Yellow badge "🏷️ Updated Price" appears when price differs
   - Tooltip shows: "Changed from Rs XXXX to Rs YYYY"

3. JavaScript functions:
   - `updatePriceIndicator()` - Shows/hides price change badge
   - Enhanced `onProductChange()` - Displays current cost
   - Enhanced `buildRow()` - Creates rows with cost columns

**User Experience:**
```
When adding item to bill:
1. Select product → Current cost (Rs 50) auto-fills
2. Change to new price (Rs 55)
3. "🏷️ Updated Price" badge appears with old price
4. Bill is saved → History recorded automatically
```

### 5. Cost Price History API
**Location:** `app/routes/purchase.py` (new endpoint)

**Endpoint:** `GET /purchase/api/product/{product_id}/cost-history`

**Response:**
```json
{
  "product_id": 1,
  "product_name": "Widget",
  "current_cost_price": 55.0,
  "total_quantity": 150,
  "history": [
    {
      "id": 1,
      "old_price": 50.0,
      "new_price": 55.0,
      "quantity_at_old_price": 100,
      "remaining_at_old_price": 100,
      "used_quantity": 0,
      "change_date": "08-04-2026 14:30",
      "reason": "Purchase bill update",
      "is_active": true,
      "purchase_bill_id": 12345
    }
  ]
}
```

### 6. Inventory Products Page Enhancement
**Location:** `app/templates/inventory/products.html`

**Changes:**
1. Added "Price History" column in products table
2. Added "History" button for each product
3. New modal displaying:
   - Current cost price and total quantity (blue alert)
   - Historical price changes in table format
   - Remaining quantity at old price marked with yellow badge
   - Full audit trail with dates and purchase bills

**Modal Display:**
```
Current Cost Price: Rs 55 | Total Quantity: 150 units

Date              Old Price  New Price  Qty@Old  Remaining  Used  Status
08-04-2026 14:30  Rs 50      Rs 55      100      🟡 100     0     ✅ Active
```

## Usage Workflow

### Creating a Bill with Price Change

```
1. Go to Purchase → Create Bill
2. Select Vendor
3. Add Item:
   - Select Product (e.g., "Widget")
   - Current Cost shows: Rs 50
   - Change to: Rs 55
   - Badge appears: "🏷️ Updated Price"
4. Save Bill
   - CostPriceHistory entry created
   - Product cost_price updated to Rs 55
   - 100 units marked as "old price" stock
   - 50 units marked as "new price" stock
```

### Viewing Price History

```
1. Go to Inventory → Products
2. Find product in table
3. Click "History" button
4. Modal shows:
   - All price changes with dates
   - Quantity at each price level
   - Remaining quantity at old prices (yet to be used)
   - Bills where prices changed
```

### Inventory Tracking

**When selling items:**
- Current system uses current cost_price for COGS
- Old price history available for reference
- `used_quantity` field tracks consumption of old-price stock
- Remaining balance shows how much of old stock is still available

## Data Consistency

### Automatic Updates
✅ Cost price updated when bill saved
✅ History entry created with old/new prices
✅ Quantity tracking automatic
✅ Date/time stamps recorded
✅ User tracking (created_by)

### Manual Adjustments
- `used_quantity` can be manually updated if stock movements recorded
- `is_active` flag can be toggled to mark as consumed
- All changes tracked in CostPriceHistory

## Benefits

1. **Complete Price Audit Trail**
   - See exactly when prices changed
   - Know which bill caused the change
   - View old vs new prices

2. **Inventory Accuracy**
   - Distinguish old-price from new-price stock
   - Track remaining at each price level
   - Better cost accounting

3. **Detailed Reports**
   - Know which items to use/sell first (FIFO)
   - Understand cost impact of price changes
   - Trace cost basis for COGS calculations

4. **Visual Indicators**
   - Yellow badge shows updated prices
   - Tooltips show previous prices
   - Modal shows full history

## Testing

### Create a test bill with price change:

```python
# Product: "Widget" currently at Rs 50 (100 units)
# Bill adds 50 units at Rs 55

# Result:
# - Product qty: 150
# - CostPriceHistory entry created
# - remaining_at_old_price: 100
# - Check via: /purchase/api/product/1/cost-history
```

### View in UI:
1. Inventory → Products → Widget → History button
2. See current price: Rs 55
3. See history: Old price Rs 50, qty 100 remaining

## Files Modified

1. **app/models.py**
   - Added CostPriceHistory model with relationships

2. **app/routes/purchase.py**
   - Updated create_bill() route to track cost changes
   - Added vendor_cost_history() API endpoint
   - Imported CostPriceHistory model

3. **app/templates/purchase/create_bill.html**
   - Added Current Cost column (read-only)
   - Added New Cost column (editable)
   - Added price change indicators (badges/tooltips)
   - Enhanced JavaScript for price tracking

4. **app/templates/inventory/products.html**
   - Added Price History column
   - Added History button
   - Added modal for viewing history
   - Added showPriceHistory() JavaScript function

5. **migrate_cost_price_history.py**
   - New migration script (executed ✅)

## Future Enhancements

1. **FIFO/LIFO Cost Method**
   - Automatically select old or new price for sales
   - Apply FIFO/LIFO methods to COGS

2. **Price Reversion**
   - Allow marking old price as fully consumed
   - Archive old price entries
   - Clean up history

3. **Cost Analysis Reports**
   - Show cost impact of price changes
   - Compare old vs new price profitability
   - Price trend analysis

4. **Alerts**
   - Notify when old price stock running low
   - Alert on significant price changes
   - Email reports on price history

5. **Integration with Sales**
   - Track which sales used old vs new price items
   - COGS calculation by price tier
   - Profit analysis by price period
