# TODO - Vendor Bank Details Implementation

## Steps
- [x] 1. Create TODO file
- [x] 2. Update `app/models.py` - Add 5 bank columns to Vendor model
- [x] 3. Update `app/forms.py` - Add 5 fields to VendorForm
- [x] 4. Update `app/routes/purchase.py` - Update add_vendor, edit_vendor, bulk upload, exports
- [x] 5. Update `app/templates/purchase/add_vendor.html` - Bank details form section
- [x] 6. Update `app/templates/purchase/edit_vendor.html` - Bank details form section
- [x] 7. Update `app/templates/purchase/vendor_profile.html` - Display bank details
- [x] 8. Update `app/templates/purchase/bill_detail.html` - Display vendor bank details
- [x] 9. Provide SQLite3 VPS queries

---

## SQLite3 Queries for VPS Server

Run these queries on your VPS SQLite database to add the new columns:

```sql
-- Add bank detail columns to vendors table
ALTER TABLE vendors ADD COLUMN bank_name VARCHAR(100);
ALTER TABLE vendors ADD COLUMN account_holder_name VARCHAR(100);
ALTER TABLE vendors ADD COLUMN account_number VARCHAR(50);
ALTER TABLE vendors ADD COLUMN swift_code VARCHAR(20);
ALTER TABLE vendors ADD COLUMN ifsc_code VARCHAR(20);
```

## Summary

Bank details have been added to the vendor module:
- **Fields**: Bank Name, Account Holder Name, Account Number, SWIFT Code, IFSC Code
- **Add Vendor**: `/purchase/vendor/add` — new "Bank Details" section in form
- **Edit Vendor**: `/purchase/vendor/edit/<id>` — new "Bank Details" section in form
- **Vendor Profile**: `/purchase/vendor/<id>` — bank details displayed in info card
- **Purchase Bill**: `/purchase/bill/<id>` — vendor bank details shown alongside vendor info
- **Bulk Upload**: Sample Excel now includes bank columns; upload parser reads them
- **Exports**: CSV, Excel, PDF exports all include bank detail rows

All fields are optional (nullable) to ensure existing data is not disturbed.

