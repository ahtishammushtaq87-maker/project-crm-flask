# Feature Visibility Troubleshooting & Fix Guide

## Summary of Issues
- Delete buttons for advances not showing in customer profile
- Advance message not appearing in Create Invoice when customer is selected
- Delivery/Advance details not visible in invoice detail view

## Root Cause Analysis
Backend code is working correctly:
- ✓ Database has customer advances stored
- ✓ Route logic is correct
- ✓ Template HTML code is present and syntactically correct
- ✓ JavaScript functions are defined
- ✓ CSS/Modal libraries are loaded

**Likely Issues:**
1. **Bootstrap Modal library** not fully loaded or conflict
2. **CSS rules** hiding elements with `display:none` or similar
3. **JavaScript errors** preventing function execution
4. **Template cache** serving old version

## Browser Debugging Steps

### Step 1: Clear All Caches
1. **Hard Refresh Browser:** Ctrl+Shift+Delete (or Cmd+Shift+Delete on Mac)
2. **Clear Application Cache:**
   - Press F12 to open Developer Tools
   - Go to "Application" tab
   - Click "Storage" in left menu
   - Click "Clear site data"
   - Check: Cookies, Storage, Cache Storage
   - Click "Clear"
3. **Restart Flask Server:**
   - Stop the running server (Ctrl+C)
   - Delete all `__pycache__` folders
   - Start fresh: `python run.py`

### Step 2: Inspect HTML Elements
1. **Open Developer Tools** (F12)
2. **Customer Profile Page** (`/sales/customer/1`):
   - Go to "Elements" / "Inspector" tab
   - Press Ctrl+F (Cmd+F on Mac)
   - Search for: `fa-trash`
   - If found: Element exists but is hidden
   - If not found: Template rendering issue
3. **Check the parent elements:**
   ```
   Right-click on delete button → Inspect Element
   Check parent <tr>, <td>, and <button> for:
   - style="display:none"
   - style="visibility:hidden"
   - style="opacity:0"
   - class="d-none" or similar Bootstrap hiding class
   ```

### Step 3: Check JavaScript Console
1. Go to "Console" tab in Developer Tools (F12)
2. Look for any red error messages
3. Common errors to look for:
   - `Uncaught ReferenceError: updateCustomerInfo is not defined`
   - `Uncaught SyntaxError:`
   - `Bootstrap/Modal errors`

### Step 4: Check Network Tab
1. Go to "Network" tab in Developer Tools
2. Reload the page (F5)
3. Check if all these files load (Status 200):
   - Bootstrap CSS files
   - Bootstrap JS files  
   - jQuery (if used)
   - Main page JS

### Step 5: Test JavaScript Directly
1. Open Console tab (F12)
2. Type this command and press Enter:
   ```javascript
   document.getElementById('customerAdvanceInfo')
   ```
3. If it returns an HTML element: Element exists but is hidden
4. If it returns `null`: Element doesn't exist in DOM

## Server-Side Fixes

### Fix #1: Force Template Recompilation
**File:** `app/__init__.py`

Add this line in the `create_app()` function to disable template caching:

```python
app.jinja_env.cache = None  # Disable Jinja2 template caching
```

This forces Flask to recompile templates on every request (only for development).

### Fix #2: Ensure Bootstrap and jQuery Are Loaded
**File:** `app/templates/base.html`

Add these lines before the closing `</body>` tag if missing:

```html
<!-- Bootstrap JS Bundle (includes Popper.js) -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

<!-- Verify Bootstrap loaded -->
<script>
    if (typeof bootstrap === 'undefined') {
        console.error('Bootstrap JS library not loaded!');
    }
</script>
```

### Fix #3: Make Delete Buttons Always Visible
**File:** `app/templates/sales/customer_profile.html` (Lines 206-240)

Change from conditional button to always-visible button (testing):

```html
<!-- BEFORE: Only shows if applied_amount == 0 -->
{% if advance.applied_amount == 0 %}
    <button class="btn btn-sm btn-outline-danger"...>
{% endif %}

<!-- AFTER: Always show button but disable if applied -->
<button class="btn btn-sm btn-outline-danger" 
        {% if advance.applied_amount > 0 %}disabled{% endif %}
        data-bs-toggle="modal" 
        data-bs-target="#deleteAdvanceModal{{ advance.id }}">
    <i class="fas fa-trash"></i>
</button>
```

### Fix #4: Simplify JavaScript for Advance Message
**File:** `app/templates/sales/create_invoice.html` (Lines 192-225)

Replace the `updateCustomerInfo()` function with a simpler version:

```javascript
function updateCustomerInfo() {
    console.log('updateCustomerInfo called');  // Debug log
    
    const select = document.getElementById('customerSelect');
    const infoDiv = document.getElementById('customerAdvanceInfo');
    
    if (!select || !infoDiv) {
        console.log('select or infoDiv not found');
        return;
    }
    
    if (select.value == '0') {
        infoDiv.style.display = 'none';
        return;
    }
    
    const selectedOption = select.options[select.selectedIndex];
    if (!selectedOption) {
        console.log('selectedOption not found');
        return;
    }
    
    const advance = selectedOption.getAttribute('data-advance') || '0';
    const total = selectedOption.getAttribute('data-total') || '0';
    
    console.log('Advance:', advance, 'Total:', total);  // Debug log
    
    // Always show the info div with data
    infoDiv.style.display = 'block';
    infoDiv.innerHTML = '<i class="fas fa-info-circle me-1"></i>' +
                        '<strong>Available Advance:</strong> Rs' + parseFloat(advance).toFixed(2) +
                        ' <span class="text-muted ms-2">|</span>' +
                        ' <strong class="ms-2">Total Received:</strong> Rs' + parseFloat(total).toFixed(2);
}

// Call on page load
document.addEventListener('DOMContentLoaded', function() {
    updateCustomerInfo();
});
```

### Fix #5: Always Show Delivery/Advance in Invoices
**File:** `app/templates/sales/invoice_detail.html` (Around line 100)

Change these lines:

```html
<!-- BEFORE: Only shows if delivery_charge > 0 -->
{% if sale.delivery_charge %}
    <div class="mb-2">
        <strong>Delivery Charge:</strong> Rs {{ '{:,.2f}'.format(sale.delivery_charge) }}
    </div>
{% endif %}

<!-- AFTER: Always show section -->
<div class="mb-2">
    <strong>Delivery Charge:</strong> Rs {{ '{:,.2f}'.format(sale.delivery_charge) }}
</div>

<!-- And same for advance applied -->
<div class="mb-2">
    <strong>Advance Applied:</strong> Rs {{ '{:,.2f}'.format(sale.advance_applied) }}
</div>
```

## Quick Test Checklist

After applying fixes:

- [ ] **Hard refresh browser** (Ctrl+Shift+R or Cmd+Shift+R)
- [ ] **Check F12 console** for any errors
- [ ] **Customer Profile**: Navigate to `/sales/customer/1`
  - [ ] See "Customer Advances" table
  - [ ] See delete buttons for unapplied advances
  - [ ] See apply buttons for advances with remaining balance
- [ ] **Create Invoice**: Go to `/sales/invoice/create`
  - [ ] Select a customer with advances
  - [ ] See blue advance info box appear
  - [ ] Shows "Available Advance" and "Total Received"
- [ ] **Invoice Detail**: View any invoice
  - [ ] See "Delivery Charge" section (even if Rs 0.00)
  - [ ] See "Advance Applied" section (even if Rs 0.00)

## If Still Not Working

### Comprehensive Reset
```bash
# 1. Stop Flask server (Ctrl+C in terminal)

# 2. Clear all caches
rm -r app/__pycache__
rm -r instance/*.db  # Or your database file location

# 3. Restart server
python run.py

# 4. Force browser cache clear
# - Press F12
# - Right-click reload button → "Empty cache and hard reload"
# - Or: Ctrl+Shift+Delete to clear all browser data
```

### Check Flask Configuration
**File:** `config.py`

Ensure caching is disabled:

```python
TEMPLATES_AUTO_RELOAD = True
SEND_FILE_MAX_AGE_DEFAULT = 0
```

### Enable Debug Mode
**File:** `run.py`

Change this line:

```python
# FROM:
app.run(debug=False)

# TO:
app.run(debug=True)
```

This will provide better error messages and auto-reload on changes.

## Database Validation

Run this to verify customer advances are in the database:

```python
from app import create_app, db
from app.models import Customer

app = create_app()
with app.app_context():
    customer = Customer.query.filter_by(name='Ahtisham Mushtaq').first()
    if customer:
        for adv in customer.advances:
            print(f"Advance {adv.id}: Rs {adv.amount}, Applied: Rs {adv.applied_amount}")
```

Expected output: Shows at least one advance with `applied_amount == 0` (eligible for delete).

---

## Summary of Changes

| Feature | File | Change | Status |
|---------|------|--------|--------|
| Delete Button Visibility | customer_profile.html | Use disabled attribute instead of hiding | Recommended |
| Advance Message | create_invoice.html | Simplify JavaScript, add logs | Recommended |
| Invoice Display | invoice_detail.html | Remove conditional, always show | Recommended |
| Template Caching | __init__.py | Disable caching in dev | Recommended |

