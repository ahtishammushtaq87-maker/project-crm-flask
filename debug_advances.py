"""
Debug script to test the advance API and check if data is being returned correctly
"""
from app import create_app, db
from app.models import Vendor, VendorAdvance
from datetime import datetime

app = create_app()

with app.app_context():
    # Check if vendors exist
    vendors = Vendor.query.all()
    print(f"\n✓ Total Vendors: {len(vendors)}")
    
    for vendor in vendors:
        print(f"\n{'='*60}")
        print(f"Vendor: {vendor.name}")
        print(f"Total Advances Given: Rs {vendor.total_advances_given:,.2f}")
        print(f"Total Advances Adjusted: Rs {vendor.total_advances_adjusted:,.2f}")
        print(f"Remaining Advance Balance: Rs {vendor.remaining_advance_balance:,.2f}")
        
        # Check advances
        advances = VendorAdvance.query.filter_by(vendor_id=vendor.id).all()
        print(f"\nAdvances ({len(advances)}):")
        for adv in advances:
            print(f"  Advance #{adv.id}:")
            print(f"    Amount: Rs {adv.amount:,.2f}")
            print(f"    Applied: Rs {adv.applied_amount:,.2f}")
            print(f"    Remaining: Rs {adv.remaining_balance:,.2f}")
            print(f"    Is Adjusted: {adv.is_adjusted}")
            if adv.adjusted_bill_id:
                print(f"    Bill ID: {adv.adjusted_bill_id}")

print(f"\n{'='*60}")
print("✓ Debug complete - check the values above")
print(f"{'='*60}\n")
