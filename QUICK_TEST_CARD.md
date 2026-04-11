# QUICK TEST CARD - Feature Visibility Fixes

## Server Status
✅ Flask server running on http://127.0.0.1:5000

## Changes Applied
1. ✅ Template caching disabled (app/__init__.py)
2. ✅ Advance message JS simplified (create_invoice.html)
3. ✅ Invoice display fixed (invoice_detail.html)
4. ✅ Delete buttons always visible (customer_profile.html)

---

## BEFORE Hard Refresh - Do This First
```
Windows: Ctrl+Shift+Delete (to clear cache)
OR
Windows: Ctrl+Shift+R (force refresh)
Mac: Cmd+Shift+R
```

Then reload each page below.

---

## Test 1: Delete Button Visibility
**URL:** http://127.0.0.1:5000/sales/customer/1

**What to Look For:**
- [ ] See "Customer Advances" table at bottom
- [ ] See trash icon (delete button) for each advance
- [ ] Advance ID 2 (Rs 500): Button should be ENABLED (clickable)
- [ ] Advance ID 1 (Rs 1000): Button should be DISABLED (grayed out)

**If Working:** You'll see red delete buttons in the Action column

---

## Test 2: Advance Message in Create Invoice
**URL:** http://127.0.0.1:5000/sales/invoice/create

**What to Look For:**
- [ ] Customer dropdown shows "Walk-in Customer" (info hidden - correct)
- [ ] Click dropdown and select customer
- [ ] Blue info box appears below showing:
  ```
  ⓘ Available Advance: Rs 550.00 | Total Received: Rs 1500.00
  ```
- [ ] Message updates when you select different customer

**If Working:** Info box appears immediately when you select a customer

---

## Test 3: Delivery & Advance in Invoice Detail
**URL:** http://127.0.0.1:5000/sales/invoice/1 (or any invoice)

**What to Look For:**
- [ ] In Summary section find:
  ```
  Subtotal: Rs X.XX
  Tax: Rs X.XX
  Discount: Rs X.XX
  Delivery Charge: Rs X.XX ← Always visible
  Advance Applied: Rs X.XX ← Always visible
  ```
- [ ] Even if Delivery is Rs 0.00, section still shows
- [ ] Even if Advance is Rs 0.00, section still shows

**If Working:** Both lines always visible in summary

---

## Troubleshooting if Features Don't Appear

### Step 1: Check Browser Console (F12)
```
1. Press F12
2. Click "Console" tab
3. Look for any RED error messages
4. Should see: "Create Invoice page loaded"
5. When you select customer, should see: "updateCustomerInfo called"
```

### Step 2: Check Page Source
```
1. Right-click on page → View Page Source (or Ctrl+U)
2. Search (Ctrl+F) for:
   - "fa-trash" → Should find delete button HTML
   - "customerAdvanceInfo" → Should find advance info div
   - "deleteAdvanceModal" → Should find delete modal
```

### Step 3: Force Full Cache Clear
```
1. F12 → Application → Storage
2. Click "Clear site data"
3. Check all boxes → Click Clear
4. Close F12
5. Ctrl+Shift+R to refresh
```

### Step 4: Restart Server
```
1. Stop Flask (Ctrl+C in terminal)
2. Wait 2 seconds
3. Run: python run.py
4. Wait for "Running on http://127.0.0.1:5000"
5. Hard refresh browser
```

---

## Quick Debug Commands (Browser F12 Console)

**Test if advance message function works:**
```javascript
document.getElementById('customerSelect')
// Should return: <select id="customerSelect"...>
```

**Test if info div exists:**
```javascript
document.getElementById('customerAdvanceInfo')
// Should return: <div id="customerAdvanceInfo"...>
```

**Manually trigger advance message:**
```javascript
updateCustomerInfo()
// Should log: "updateCustomerInfo called"
```

**Check if Bootstrap is loaded:**
```javascript
typeof bootstrap
// Should return: "object"
```

---

## Expected Behavior Summary

| Feature | Before Fix | After Fix |
|---------|-----------|-----------|
| **Delete Buttons** | Hidden/not showing | Always visible (disabled if applied) |
| **Advance Message** | Not appearing on select | Shows immediately in blue box |
| **Delivery/Advance** | Only shown if > 0 | Always shown in summary |
| **Template Caching** | Old version served | Fresh version on each request |

---

## Login Credentials (if needed)
- **Username:** testuser
- **Password:** (Check with admin or see in database)
- **Or:** Username: admin (check your records)

---

## Database Test (Run in Terminal)
```bash
python -c "
from app import create_app, db
from app.models import Customer

app = create_app()
with app.app_context():
    c = Customer.query.filter_by(name='Ahtisham Mushtaq').first()
    if c:
        for adv in c.advances:
            print(f'Advance {adv.id}: Rs {adv.amount:.2f}, Applied: Rs {adv.applied_amount:.2f}')
"
```

Should show:
```
Advance 1: Rs 1000.00, Applied: Rs 950.00
Advance 2: Rs 500.00, Applied: Rs 0.00
```

---

## File Locations
- Server running from: `d:\prefex_flask\project_crm_flask\project_crm_flask`
- Main app file: `app/__init__.py`
- Templates: `app/templates/sales/`
- Routes: `app/routes/sales.py`
- Models: `app/models.py`

---

## Success Criteria - All Pass = Features Working ✅

- [ ] Delete button visible in customer profile
- [ ] Advance message appears in create invoice
- [ ] Delivery charge visible in invoice detail
- [ ] Advance applied visible in invoice detail
- [ ] No errors in browser F12 console
- [ ] All Bootstrap modals work (click delete button opens modal)

---

**Last Updated:** After implementing all 4 fixes
**Server Status:** Running and Ready for Testing

