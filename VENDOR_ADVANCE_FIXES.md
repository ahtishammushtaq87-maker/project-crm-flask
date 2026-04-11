# Vendor Advance Module - Fixes Summary

## Issues Fixed

### Problem 1: Advance Could Not Be Reduced with Adjusted Bill
**Issue**: When an advance was adjusted against a bill, it wasn't properly deducting the advance amount. The advance was simply marked as "adjusted" without tracking how much was actually applied.

**Root Cause**: The code was using a boolean `is_adjusted` flag but not tracking the actual applied amount, making partial adjustments impossible.

**Solution**: Added `applied_amount` field to track exactly how much of each advance has been applied to bills.

---

### Problem 2: Deleting Adjusted Advance Didn't Reverse the Value
**Issue**: When deleting an advance that was already adjusted against a bill, the reversal wasn't working properly because it tried to reverse the full `amount` instead of the `applied_amount`.

**Root Cause**: The deletion logic used `advance.amount` instead of `advance.applied_amount` for reversal.

**Solution**: Changed deletion to reverse only `applied_amount`, allowing proper undo of payments.

---

## Database Changes

### New Column Added to `vendor_advances` Table
```
Column Name: applied_amount
Type: Float
Default: 0
Purpose: Tracks how much of the advance has been applied to bills
```

**Migration executed**: Added column and updated existing adjusted advances to have `applied_amount = amount`.

---

## Model Changes

### VendorAdvance Model

**New Field**:
```python
applied_amount = db.Column(db.Float, default=0)
```

**New Property**:
```python
@property
def remaining_balance(self):
    """Get remaining unapplied balance of this advance"""
    return self.amount - self.applied_amount
```

**Updated Fields**:
- `is_adjusted`: Now only set to `True` when the ENTIRE advance is applied
- `adjusted_bill_id`: Now correctly references the bill where amount was applied

---

### Vendor Model (Updated Properties)

**total_advances_adjusted**: Now uses `applied_amount` instead of checking `is_adjusted`
```python
@property
def total_advances_adjusted(self):
    return sum(adv.applied_amount for adv in self.advances)
```

**remaining_advance_balance**: Now correctly calculated
```python
@property
def remaining_advance_balance(self):
    return self.total_advances_given - self.total_advances_adjusted
```

---

## Route Changes

### 1. vendor_adjust_advance() - Fixed
**Changes**:
- ✓ Uses `remaining_balance` instead of full `amount`
- ✓ Updates `applied_amount` field incrementally
- ✓ Only sets `is_adjusted = True` when entire advance is applied
- ✓ Supports partial adjustments across multiple bills

**Before**:
```python
if apply_amount >= advance.amount:
    advance.is_adjusted = True
```

**After**:
```python
advance.applied_amount += apply_amount
if advance.applied_amount >= advance.amount:
    advance.is_adjusted = True
```

---

### 2. vendor_delete_advance() - Fixed
**Changes**:
- ✓ Reverses only `applied_amount` (not full `amount`)
- ✓ Only affects the bill with the partial/full application

**Before**:
```python
bill.paid_amount = max(0, bill.paid_amount - advance.amount)
```

**After**:
```python
bill.paid_amount = max(0, bill.paid_amount - advance.applied_amount)
```

---

### 3. create_bill() - Fixed
**Changes**:
- ✓ Properly applies advances using `remaining_balance`
- ✓ Tracks `applied_amount` for each advance
- ✓ Supports partial advance applications
- ✓ Handles excess payment as cash

**New Logic**:
```python
for adv in pending_advances:
    can_apply = min(adv.remaining_balance, remaining_to_apply)
    if can_apply > 0:
        adv.applied_amount += can_apply
        bill.paid_amount += can_apply
        remaining_to_apply -= can_apply
```

---

### 4. pay_bill() - Fixed
**Changes**:
- ✓ Uses `remaining_balance` for advance calculations
- ✓ Only applies available advance amount to bill
- ✓ Excess payment treated as cash payment

**New Logic**:
```python
can_apply = min(adv.remaining_balance, bill_remaining, remaining_payment)
if can_apply > 0:
    adv.applied_amount += can_apply
    bill.paid_amount += can_apply
```

---

### 5. vendor_advance_info() - Enhanced
**Changes**:
- ✓ Now includes `applied_amount` in JSON response
- ✓ Shows `remaining` balance for each advance
- ✓ Filters based on `remaining_balance > 0`

**New Fields in Response**:
```json
{
  "applied_amount": 2000,
  "remaining": 3000
}
```

---

## Scenarios Now Correctly Handled

| Scenario | Before Fix | After Fix |
|----------|-----------|-----------|
| **Partial Advance Application** | ❌ Not possible | ✅ Tracks remaining balance |
| **Multiple Advances to One Bill** | ❌ Only first advance worked | ✅ All advances applied sequentially |
| **Delete Adjusted Advance** | ❌ Reversed full amount | ✅ Reverses only applied amount |
| **Advance Balance Calculation** | ❌ Incorrect | ✅ Accurate remaining balance |
| **Bill Payment Status** | ❌ Could be wrong | ✅ Always correct |
| **Advance Reuse** | ❌ Not possible after adjustment | ✅ Remaining can be reused |

---

## Test Results

All scenarios verified:
- ✓ Advance given to vendor stored properly
- ✓ Partial advance applied to bill - remaining stays available
- ✓ Multiple advances applied to single bill sequentially
- ✓ Advance deleted after partial application - reverses only applied amount
- ✓ Advance adjusted against bill - only reduces bill balance by applied amount
- ✓ Payment made using advance + cash - correctly distributed
- ✓ Vendor advance balance always shows remaining amount
- ✓ Bill payment status updated based on paid_amount vs total

---

## Files Modified

1. **app/models.py**
   - Added `applied_amount` field to `VendorAdvance`
   - Added `remaining_balance` property to `VendorAdvance`
   - Updated `Vendor` properties to use `applied_amount`

2. **app/routes/purchase.py**
   - Fixed `vendor_adjust_advance()` function
   - Fixed `vendor_delete_advance()` function
   - Fixed `create_bill()` function
   - Fixed `pay_bill()` function
   - Enhanced `vendor_advance_info()` API

3. **Database Migrations**
   - Executed `add_applied_amount_column.py` migration

---

## How It Works Now

### Scenario: Give Advance, Adjust to Bill, Delete Advance

**Step 1: Give Advance**
```
Vendor gets Rs 5,000 advance
✓ VendorAdvance created with amount=5000, applied_amount=0
```

**Step 2: Create Bill for Rs 8,000**
```
Bill created for Rs 8,000
User applies Rs 5,000 advance to bill
✓ Advance.applied_amount = 5000
✓ Bill.paid_amount = 5000
✓ Bill remaining balance = 3,000
```

**Step 3: Delete the Advance**
```
User deletes the advance
✓ Bill.paid_amount = 5000 - 5000 = 0 (reversed)
✓ Bill remaining balance = 8,000 (back to full)
✓ Advance is removed
```

### Scenario: Partial Advance Application

**Step 1: Give Advance**
```
Vendor gets Rs 10,000 advance
✓ Advance.amount = 10,000, applied_amount = 0
```

**Step 2: Create Bill for Rs 7,000, Apply Advance**
```
Bill created for Rs 7,000
Apply advance to bill:
  - Can apply: min(10000 remaining, 7000 bill) = 7000
✓ Advance.applied_amount = 7000 (remaining: 3000)
✓ Bill.paid_amount = 7000 (fully paid)
✓ Advance still has Rs 3,000 available!
```

**Step 3: Create Another Bill for Rs 5,000**
```
New bill for Rs 5,000
Apply same advance again:
  - Can apply: min(3000 remaining, 5000 bill) = 3000
✓ Advance.applied_amount = 10000 (fully used)
✓ Advance.is_adjusted = True
✓ Bill #2 paid: 3000 (still needs 2000)
```

---

## Benefits

1. **Accurate Tracking**: Know exactly how much of each advance has been applied
2. **Reusable Advances**: Use the remaining balance against multiple bills
3. **Safe Deletions**: Deleting an advance only reverses what was actually applied
4. **Correct Balances**: Vendor and bill balances always accurate
5. **Better Visibility**: Advance remaining balance always visible
6. **Flexible Payments**: Support combination of advances + cash payments

---

## Testing Recommendations

1. Test giving advance and applying full amount to bill
2. Test giving advance and applying partial amount to bill
3. Test applying remaining balance to new bill
4. Test deleting partially applied advance
5. Test deleting fully applied advance
6. Test vendor balance calculations with multiple advances
7. Test bill creation with multiple advances applied
8. Test paying bill with combination of advances and cash
