# Cost Price History System - Testing Checklist

## ✅ System Status: READY

Database verified ✅
Models created ✅
Routes updated ✅
UI enhanced ✅
API working ✅

---

## 🧪 Test Scenarios

### Test 1: Create Bill with Price Change

**Steps:**
1. Navigate to: **Purchase → Create Bill**
2. Select **Vendor** (e.g., "Test Vendor")
3. Click **"Add Item"** button
4. Select **Product** (should have at least 1 product with cost_price set)
5. Observe:
   - ✅ "Current Cost" column shows existing cost_price
   - ✅ "New Cost" auto-fills with current cost
6. Change "New Cost" to a different value (e.g., from 100 to 150)
7. Observe:
   - ✅ Yellow badge "🏷️ Updated Price" appears
   - ✅ Hovering shows tooltip with old price
8. Enter Quantity and other details
9. Click **"Save Bill"**
10. Verify:
    - ✅ Bill created successfully
    - ✅ No errors in console
    - ✅ Product quantity increased

**Expected Result:** ✅ Bill saved, CostPriceHistory entry created

---

### Test 2: Check Cost Price History

**Steps:**
1. Navigate to: **Inventory → Products**
2. Find the product you just modified
3. Look for **"Price History"** column
4. Click **"History"** button
5. Modal opens showing:
   - ✅ Current Cost Price
   - ✅ Total Quantity
   - ✅ Table with price changes
   - ✅ Old price, New price, Quantity info
   - ✅ Remaining quantity with yellow badge
   - ✅ Status indicator (Active/Consumed)

**Expected Result:** ✅ Modal shows accurate price history data

---

### Test 3: Multiple Price Changes

**Steps:**
1. Create another bill with the same product
2. Change price again (e.g., from 150 to 120)
3. Save bill
4. Go to **Inventory → Products → Product → History**
5. Verify:
   - ✅ Multiple entries in history table
   - ✅ Most recent change at top
   - ✅ Each entry shows correct old/new prices
   - ✅ Remaining quantities update correctly

**Expected Result:** ✅ History shows all price changes in reverse chronological order

---

### Test 4: API Endpoint

**Steps:**
1. Open browser developer console (F12)
2. Go to: **Inventory → Products → Any Product → History**
3. In console, check Network tab
4. Look for request to `/purchase/api/product/{id}/cost-history`
5. Verify response contains:
   - ✅ product_id and product_name
   - ✅ current_cost_price
   - ✅ total_quantity
   - ✅ history array with entries

**Expected Result:** ✅ API returns complete JSON data

---

### Test 5: No Price Change (Should Not Create History)

**Steps:**
1. Create a bill with items
2. For each item, use the SAME price as current cost_price
3. Do NOT change the price
4. Save bill
5. Go to **Inventory → Products → History**
6. Verify:
   - ✅ No new history entry created (if this was first purchase at that price)
   - OR ✅ Most recent entry has updated quantity

**Expected Result:** ✅ Only entries for price changes are recorded

---

### Test 6: Visual Indicators

**Steps:**
1. Go to **Purchase → Create Bill**
2. Add product at different prices
3. Verify visual elements:
   - ✅ Current Cost column has gray background (read-only)
   - ✅ New Cost column is white (editable)
   - ✅ Yellow badge appears when prices differ
   - ✅ Badge shows "🏷️ Updated Price"
   - ✅ Tooltip shows old price on hover

**Expected Result:** ✅ All visual indicators display correctly

---

### Test 7: Database Records

**Steps:**
1. Run: `python verify_cost_history.py`
2. Verify output shows:
   - ✅ cost_price_history table exists
   - ✅ CostPriceHistory model working
   - ✅ Product count correct
   - ✅ Relationships accessible

**Expected Result:** ✅ All database checks pass

---

## 📋 Automated Verification

Run this command:
```bash
cd d:\prefex_flask\project_crm_flask\project_crm_flask
python verify_cost_history.py
```

Expected output:
```
✅ cost_price_history table exists
✅ CostPriceHistory model working
✅ N products in database
✅ Product.cost_price_changes relationship exists
```

---

## 🔍 Manual Browser Testing

### Create Bill Form
- [ ] "Current Cost" column visible
- [ ] "New Cost" column visible and editable
- [ ] Yellow badge appears on price change
- [ ] Tooltip shows old price
- [ ] Bill saves without errors

### Inventory Products
- [ ] "Price History" column visible
- [ ] "History" button on each row
- [ ] Modal opens on button click
- [ ] Modal shows correct data
- [ ] No console errors

### Modal Display
- [ ] Current price displayed
- [ ] Total quantity shown
- [ ] History table populated
- [ ] Yellow badges on remaining qty
- [ ] Status column shows correctly

---

## 🐛 Troubleshooting

### Issue: Yellow badge not appearing

**Solution:**
1. Check developer console (F12) for errors
2. Verify product has cost_price set
3. Change price to value different from current
4. Refresh page if needed

### Issue: History modal shows blank

**Solution:**
1. Check Network tab in F12 - is API call working?
2. Verify product ID is correct
3. Check server logs for errors
4. Ensure cost_price_history table was created

### Issue: "Current Cost" showing 0 or blank

**Solution:**
1. Product might not have cost_price set
2. Go to Inventory → Edit Product
3. Set a cost price value
4. Try again

### Issue: App won't start after changes

**Solution:**
1. Check Python syntax: `python -m py_compile app/models.py`
2. Verify imports: `python -c "from app.models import CostPriceHistory"`
3. Run migration again: `python migrate_cost_price_history.py`

---

## ✅ Sign-Off Checklist

**Before considering complete:**

- [ ] Database table created and verified
- [ ] CostPriceHistory model working
- [ ] create_bill() tracks cost changes
- [ ] Bill form shows Current Cost column
- [ ] Bill form shows New Cost column
- [ ] Yellow badge appears on price change
- [ ] Price history modal displays
- [ ] API endpoint returns correct JSON
- [ ] No console errors in browser
- [ ] No server errors in logs
- [ ] Multiple price changes tracked correctly
- [ ] Non-price-change bills don't create history
- [ ] All visual indicators working
- [ ] Verification script passes all checks

---

## 📊 Sample Test Data

### Test Product
- **Name:** Widget
- **Current Cost:** Rs 50
- **Quantity:** 100 units

### Test Purchase Bill 1
- **Date:** Today
- **Item:** Widget
- **Qty:** 50
- **New Price:** Rs 55
- **Expected:** History created with old=50, new=55, qty@old=100, remaining=100

### Test Purchase Bill 2
- **Date:** Today (later)
- **Item:** Widget
- **Qty:** 25
- **New Price:** Rs 60
- **Expected:** History created with old=55, new=60, qty@old=150, remaining=150

### Check History
Should show 2 entries:
1. Rs 55 → Rs 60 (qty: 150, remaining: 150)
2. Rs 50 → Rs 55 (qty: 100, remaining: 100)

---

## 🎯 Success Criteria

✅ **System is COMPLETE** when:

1. Database migration successful
2. Models properly defined and accessible
3. Purchase bills track cost price changes
4. Visual indicators show in UI
5. History viewable and accurate
6. No database errors or conflicts
7. API returns correct data
8. All tests pass without errors

---

## 📞 Quick Reference

| Component | File | Location |
|-----------|------|----------|
| Model | models.py | Line ~930 |
| Migration | migrate_cost_price_history.py | Root directory |
| Route Handler | purchase.py | create_bill() function |
| API | purchase.py | product_cost_history() function |
| Bill Form | create_bill.html | Item table section |
| Inventory UI | products.html | Price history modal |

---

## 🚀 Next Steps

1. Test all scenarios above
2. Create sample bills with price changes
3. Verify history displays correctly
4. Check API responses
5. Review console for any errors
6. If all pass: ✅ **IMPLEMENTATION COMPLETE**

---

Last Updated: April 8, 2026
Status: ✅ READY FOR TESTING
