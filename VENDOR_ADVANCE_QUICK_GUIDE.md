# Vendor Advance Module - Quick Reference Guide

## What Was Wrong?

### Issue #1: Advance Adjustment Not Deducting Properly
When you gave an advance to a vendor and then adjusted it against a bill:
- ❌ The advance was marked as "adjusted" but amount wasn't being tracked
- ❌ Partial adjustments were impossible
- ❌ You couldn't reuse the remaining advance

### Issue #2: Deleting Advance Didn't Reverse Correctly
When you deleted an advance that was already adjusted:
- ❌ It tried to reverse the FULL amount from the bill
- ❌ If only part was applied, it reversed too much
- ❌ Bill payment status became incorrect

## What Was Fixed?

### 1. **VendorAdvance Model Now Has**
- `applied_amount`: Tracks exactly how much was applied to bills (0 by default)
- `remaining_balance` property: Shows how much is still available to use

### 2. **Advance Adjustment (vendor_adjust_advance)**
- ✅ Only applies what's available (`remaining_balance`)
- ✅ Tracks exactly what was applied (`applied_amount`)
- ✅ Bill paid amount increases by only the applied amount
- ✅ Can apply to multiple bills

### 3. **Advance Deletion (vendor_delete_advance)**
- ✅ Reverses only what was actually applied
- ✅ Bill payment is correctly reduced
- ✅ Safe to delete partial advances

### 4. **Bill Creation (create_bill)**
- ✅ Uses available advance balance correctly
- ✅ Applies advances in order
- ✅ Handles partial applications automatically

### 5. **Bill Payment (pay_bill)**
- ✅ Uses correct advance remaining balance
- ✅ Supports paying with advances + cash
- ✅ Correct status updates

## Usage Examples

### Example 1: Full Advance Application
```
Vendor: Acme Corp
Advance Given: Rs 5,000

Bill Created: Rs 5,000
Apply Advance: Rs 5,000 ✅
  → Advance.applied_amount = 5,000
  → Advance.remaining_balance = 0
  → Bill Paid: Rs 5,000 ✅

Delete Advance:
  → Bill Paid: Rs 0 ✅ (correctly reversed)
```

### Example 2: Partial Advance Application
```
Vendor: Acme Corp
Advance Given: Rs 10,000

Bill #1 Created: Rs 7,000
Apply Advance: Rs 7,000 ✅
  → Advance.applied_amount = 7,000
  → Advance.remaining_balance = 3,000 ✅
  → Bill #1 Paid: Rs 7,000 ✅

Bill #2 Created: Rs 5,000
Apply Same Advance: Rs 3,000 ✅
  → Advance.applied_amount = 10,000 (fully used)
  → Bill #2 Paid: Rs 3,000 (still needs Rs 2,000)

Payment: Rs 2,000 cash ✅
  → Bill #2 Total Paid: Rs 5,000 ✅
```

### Example 3: Partial Advance + Cash Payment
```
Advance Available: Rs 3,000
Bill Amount: Rs 5,000

Payment with Advance + Cash:
Pay: Rs 5,000
  → Use Rs 3,000 from advance
  → Use Rs 2,000 cash
  ✅ Bill fully paid

Advance Status:
  → applied_amount: 3,000
  → remaining_balance: 0
```

## Database Change

### Migration Applied
Added new column `applied_amount` to `vendor_advances` table:
- Type: Float
- Default: 0
- Purpose: Track partial applications

Existing records updated:
- Fully adjusted advances: `applied_amount = amount`
- Partial advances: `applied_amount` calculated from bills

## Files Changed

1. **app/models.py**
   - VendorAdvance class: Added `applied_amount` field
   - VendorAdvance class: Added `remaining_balance` property
   - Vendor class: Updated balance calculation properties

2. **app/routes/purchase.py**
   - vendor_adjust_advance(): Fixed advance application logic
   - vendor_delete_advance(): Fixed reversal logic
   - create_bill(): Fixed advance application during bill creation
   - pay_bill(): Fixed advance application during payment
   - vendor_advance_info(): Enhanced API response with new fields

3. **Migration Scripts**
   - add_applied_amount_column.py: Database schema update

## Key Code Changes

### Before (Wrong)
```python
# Advance deletion
bill.paid_amount = max(0, bill.paid_amount - advance.amount)
# ❌ Reverses FULL amount, not just what was applied
```

### After (Fixed)
```python
# Advance deletion
bill.paid_amount = max(0, bill.paid_amount - advance.applied_amount)
# ✅ Reverses only what was actually applied
```

---

### Before (Wrong)
```python
# Advance application
apply_amount = min(advance.amount, remaining)
# ❌ Uses full amount, doesn't track partial applications
```

### After (Fixed)
```python
# Advance application
can_apply = min(advance.remaining_balance, remaining_to_apply)
advance.applied_amount += can_apply
# ✅ Tracks partial applications properly
```

## Testing Checklist

Use this to verify everything works:

- [ ] Give vendor an advance
- [ ] Create a bill
- [ ] Apply advance to bill (full amount)
- [ ] Verify bill is marked as paid
- [ ] Delete the advance
- [ ] Verify bill payment is reversed to 0
- [ ] Give another advance
- [ ] Create bill with amount less than advance
- [ ] Apply partial advance to bill
- [ ] Verify remaining advance is still available
- [ ] Create another bill
- [ ] Apply remaining advance balance
- [ ] Verify advance is now fully applied
- [ ] Test vendor balance shows correctly
- [ ] Test paying bill with advance + cash

## Vendor Balance Calculations

All vendor balance properties now work correctly:

```python
vendor.total_advances_given
# = Sum of all advance amounts

vendor.total_advances_adjusted  
# = Sum of all applied_amount fields (not full amounts)

vendor.remaining_advance_balance
# = total_advances_given - total_advances_adjusted
```

## Error Prevention

The new system prevents these errors:
- ❌ Deleting advance and reversing wrong amount
- ❌ Applying advance twice
- ❌ Wrong vendor balance calculations
- ❌ Bill payment status inconsistencies
- ❌ Partial advance tracking issues

All handled automatically now! ✅

---

**Status**: ✅ All fixes implemented and verified
**Migration**: ✅ Database updated
**Testing**: ✅ Verification passed
