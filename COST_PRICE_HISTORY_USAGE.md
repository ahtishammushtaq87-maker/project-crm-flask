# Cost Price History System - Quick Start Guide

## 🎯 What This Does

When you purchase items at a new price, the system:
1. **Marks items with old price** - Shows remaining quantity at previous price
2. **Updates product cost price** - Sets new cost for future calculations
3. **Creates audit trail** - Records all price changes with dates and bills
4. **Shows visual indicators** - Yellow badges mark price-changed items

## 📝 Step-by-Step Usage

### Example Scenario
- Product: **Widget**
- Current stock: **100 units** at **Rs 50 each**
- New purchase: **50 units** at **Rs 55 each**

### Step 1: Create Purchase Bill

Navigate to: **Purchase** → **Create Bill**

```
1. Select Vendor (e.g., "ABC Supplier")
2. Click "Add Item"
3. Select Product: "Widget"
   ✅ Current Cost auto-shows: Rs 50
4. Enter Quantity: 50
5. Change Price to: 55
   ⚠️ Yellow badge appears: "🏷️ Updated Price"
   Tooltip shows: "Changed from Rs 50"
6. Click "Save Bill"
```

### Step 2: Verify Changes

After saving:
- **Product Quantity:** 150 units (100 old + 50 new)
- **Product Cost Price:** Updated to Rs 55
- **CostPriceHistory Entry Created:**
  - Old price: Rs 50 (100 units)
  - New price: Rs 55 (50 units)
  - Remaining at old price: 100 units

### Step 3: View Price History

Navigate to: **Inventory** → **Products**

```
1. Find "Widget" in the table
2. Click "📊 History" button
3. Modal opens showing:
   
   ✅ CURRENT STATUS
   Current Cost Price: Rs 55 | Total Quantity: 150 units
   
   📊 PRICE HISTORY TABLE
   Date              | Old Price | New Price | Qty@Old | Remaining | Status
   08-04-2026 14:30  | Rs 50     | Rs 55     | 100     | 🟡 100    | ✅ Active
   
   Legend:
   🟡 Remaining = Stock still available at old price (not yet used)
```

## 🎨 Visual Indicators

### In Bill Creation Form
```
Current Cost     │ New Cost (Editable)
─────────────────┼─────────────────────────
Rs 50 (gray)     │ 55 🏷️ Updated Price
                 │    ↑ Tooltip: "Changed from Rs 50"
```

### In Price History Modal
```
Date            Old Price  New Price  Qty@Old  Remaining  Used  Status
─────────────────────────────────────────────────────────────────────────
08-04-2026      Rs 50      Rs 55      100      🟡 100     0     ✅ Active
14:30
```

**Color Meanings:**
- 🟡 Yellow Badge = Remaining quantity at old price
- ✅ Green = Price actively in use
- ⏹️ Gray = Price fully consumed

## 💾 Data Structure

### CostPriceHistory Entry Example

```
{
  "product_id": 1,
  "product_name": "Widget",
  "old_price": 50.0,
  "new_price": 55.0,
  "quantity_at_old_price": 100,        ← Stock at old price when change occurred
  "remaining_at_old_price": 100,       ← Still available (not yet sold)
  "used_quantity": 0,                  ← Already sold at old price
  "change_date": "08-04-2026 14:30",
  "reason": "Purchase bill PO-202604-0001",
  "is_active": true,
  "purchase_bill_id": 1
}
```

## 🔍 Real-World Example

### Purchase History of "Gadget" Product

```
Timeline:
────────────────────────────────────────────────────────────────

Jan 1, 2026: Buy 100 units @ Rs 100 each (Current Cost: Rs 100)
             → Stock: 100 @ Rs 100

Feb 15, 2026: Buy 50 units @ Rs 110 each (Current Cost updated: Rs 110)
              → Stock: 100 @ Rs 100 + 50 @ Rs 110
              → CostPriceHistory shows:
                * Old price: Rs 100, Qty: 100, Remaining: 100
                * New price: Rs 110

Apr 8, 2026: Buy 75 units @ Rs 105 each (Current Cost updated: Rs 105)
             → Stock: 100 @ Rs 100 + 50 @ Rs 110 + 75 @ Rs 105
             → CostPriceHistory shows:
               * Entry 1: Rs 100 → Rs 110, Remaining: 100
               * Entry 2: Rs 110 → Rs 105, Remaining: 50

History Modal View:
───────────────────
Current Cost: Rs 105 | Total Qty: 225 units

Date             Old Price  New Price  Qty@Old  Remaining  Used  Status
────────────────────────────────────────────────────────────────────────
08-04-2026       Rs 110     Rs 105     50       🟡 50      0     ✅ Active
15-02-2026       Rs 100     Rs 110     100      🟡 100     0     ✅ Active
01-01-2026       —          Rs 100     —        —          0     ✅ Complete
```

## 🛠️ API Reference

### Get Cost Price History for Product

**Endpoint:**
```
GET /purchase/api/product/{product_id}/cost-history
```

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
      "purchase_bill_id": 1
    }
  ]
}
```

## ❓ Common Questions

**Q: Will old stock be automatically consumed first (FIFO)?**
A: Not yet. Manual tracking available in remaining_at_old_price field. Future enhancement planned.

**Q: Can I revert a price change?**
A: Yes, create a new bill with the old price. It will create a new CostPriceHistory entry.

**Q: How does this affect COGS?**
A: Current system uses current_cost_price. Old prices available for reference and manual COGS allocation.

**Q: Can I see which sales used old-price items?**
A: Tracking available through CostPriceHistory. Full integration with sales reports coming soon.

**Q: What if I make a mistake entering the price?**
A: Edit the bill before finalizing, or create an adjustment bill with correct price.

## 📊 Benefits

✅ **Complete Audit Trail** - See all price changes with dates and bills
✅ **Inventory Accuracy** - Know exactly how much at each price level
✅ **Cost Tracking** - Track cost basis for accounting
✅ **Visual Clarity** - Badges and modals make history obvious
✅ **Easy Lookup** - One click to view entire price history

## 🚀 Future Features

🔄 FIFO/LIFO automatic cost method
📧 Price change alerts
💹 Cost trend analysis
📈 Profitability reports by price tier
🔗 Integration with sales tracking
