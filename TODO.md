# Sales Invoice Enhancement TODO

## Plan
1. [x] app/models.py - Add image_path to Payment model
2. [x] app/routes/sales.py - Update pay_invoice() + add image route
3. [x] app/templates/sales/invoice_detail.html - Customer link + payment form + history
4. [x] Create migration script for payments.image_path column
5. [x] Test and verify migration
6. [x] Provide SQL query for VPS deployment

## Status: COMPLETE

## Changes Made:
- **app/models.py**: Added `image_path = db.Column(db.String(255))` to Payment model
- **app/routes/sales.py**:
  - Added `Payment`, `PaymentMethod` to imports
  - `invoice_detail()` now queries payment_methods and payments, passes `today`
  - `pay_invoice()` enhanced to handle file uploads and create Payment records
  - New route `/payment/<int:payment_id>/image` to serve receipt images
- **app/templates/sales/invoice_detail.html**:
  - Customer name is now a clickable link to customer profile
  - Due date displayed if set
  - Payment form upgraded with date, method dropdown, receipt image upload, notes
  - Payment History table shows all payments with dates, methods, amounts, and receipt images
- **migrate_payment_image.py**: SQLite migration script for adding image_path column

## VPS Deployment SQL (SQLite):
```sql
-- Run this on your VPS database if image_path column doesn't exist
ALTER TABLE payments ADD COLUMN image_path VARCHAR(255);
```

## Files Modified:
- app/models.py
- app/routes/sales.py
- app/templates/sales/invoice_detail.html

## Files Created:
- migrate_payment_image.py

