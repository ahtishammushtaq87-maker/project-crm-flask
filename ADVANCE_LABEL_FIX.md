# Fix Summary: Advance Label Display Issue

## Problem
The "Advance Paid" label showing remaining advance balance was not displaying on the bill creation form when selecting a vendor.

## Root Cause
**API Endpoint URL Mismatch**: The JavaScript was fetching from `/api/vendor/{id}/advances` but the correct URL should be `/purchase/api/vendor/{id}/advances` because the purchase routes are registered under the `/purchase` blueprint prefix.

## Solution Applied

### Files Modified:
1. **app/templates/purchase/create_bill.html**
   - Line ~267: Changed `fetch('/api/vendor/${vendorId}/advances')` to `fetch('/purchase/api/vendor/${vendorId}/advances')`
   - Line ~336: Changed `fetch('/api/vendor/${vendorId}/purchase-orders')` to `fetch('/purchase/api/vendor/${vendorId}/purchase-orders')`

2. **app/templates/purchase/bill_detail.html**
   - Line ~344: Changed `fetch('/api/vendor/${vendorId}/advances')` to `fetch('/purchase/api/vendor/${vendorId}/advances')`

## Verification

✓ API endpoint tested and returning correct data:
```json
{
  "pending_balance": 19000.0,
  "total_advances": 30000.0,
  "total_adjusted": 11000.0,
  "advances": [
    {
      "amount": 30000.0,
      "applied_amount": 11000.0,
      "remaining": 19000.0,
      ...
    }
  ]
}
```

✓ App initialization successful

## Expected Behavior After Fix

When creating a bill and selecting a vendor:
1. The JavaScript fetches advance data from `/purchase/api/vendor/{id}/advances`
2. The advance label displays: "Rs 19,000 remaining" (for test vendor)
3. The "Use Advance" button shows the available amount
4. Real-time calculations work correctly when applying advance

## Testing
Navigate to: http://127.0.0.1:5000/purchase/bill/create
- Select "Test Vendor" from dropdown
- Verify "Advance Paid" section shows "Rs 19,000 remaining"
- Check developer console (F12) for debug logs confirming data fetch
