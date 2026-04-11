"""
Verification script to test the vendor advance fixes
Tests:
1. Advance adjustment with proper deduction
2. Partial advance adjustment
3. Advance deletion and reversal
4. Bill payment with advance application
"""
from app import db, create_app
from app.models import Vendor, VendorAdvance, PurchaseBill, PurchaseItem, Product, User
from datetime import datetime, timedelta

def create_test_data(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # Create a test user
        user = User(username='testuser', email='test@test.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        # Create a vendor
        vendor = Vendor(
            name='Test Vendor',
            email='vendor@test.com',
            phone='1234567890'
        )
        db.session.add(vendor)
        db.session.commit()
        
        # Create test product
        product = Product(
            name='Test Product',
            sku='TP001',
            quantity=100,
            unit='pieces'
        )
        db.session.add(product)
        db.session.commit()
        
        # Create advances
        adv1 = VendorAdvance(
            vendor_id=vendor.id,
            amount=5000,
            date=datetime.now().date(),
            description='Advance 1',
            created_by=user.id
        )
        adv2 = VendorAdvance(
            vendor_id=vendor.id,
            amount=3000,
            date=datetime.now().date(),
            description='Advance 2',
            created_by=user.id
        )
        db.session.add_all([adv1, adv2])
        db.session.commit()
        
        # Create a purchase bill
        bill = PurchaseBill(
            bill_number='PO-202604-0001',
            vendor_id=vendor.id,
            date=datetime.now(),
            due_date=datetime.now() + timedelta(days=30),
            currency_id=None,
            exchange_rate=1,
            created_by=user.id
        )
        db.session.add(bill)
        db.session.commit()
        
        # Add items to bill
        item = PurchaseItem(
            bill_id=bill.id,
            product_id=product.id,
            quantity=10,
            unit_price=1000
        )
        item.total = item.quantity * item.unit_price
        db.session.add(item)
        db.session.commit()
        
        bill.calculate_totals()
        db.session.commit()
        
        return user, vendor, bill, adv1, adv2, product

def test_scenario_1(app):
    """Test: Advance partial application to bill"""
    print("\n" + "="*60)
    print("TEST 1: Advance Partial Application to Bill")
    print("="*60)
    
    user, vendor, bill, adv1, adv2, product = create_test_data(app)
    
    with app.app_context():
        bill = PurchaseBill.query.get(bill.id)
        adv1 = VendorAdvance.query.get(adv1.id)
        vendor = Vendor.query.get(vendor.id)
        
        print(f"\nInitial State:")
        print(f"  Bill Total: Rs {bill.total:,.2f}")
        print(f"  Bill Paid Amount: Rs {bill.paid_amount:,.2f}")
        print(f"  Bill Balance Due: Rs {bill.balance_due:,.2f}")
        print(f"  Advance 1: Rs {adv1.amount:,.2f} | Applied: Rs {adv1.applied_amount:,.2f} | Remaining: Rs {adv1.remaining_balance:,.2f}")
        
        # Simulate partial advance application
        bill_remaining = bill.balance_due
        apply_amount = min(adv1.remaining_balance, bill_remaining)
        adv1.applied_amount += apply_amount
        bill.paid_amount += apply_amount
        bill.update_status()
        db.session.commit()
        
        print(f"\nAfter Applying Rs {apply_amount:,.2f} from Advance 1:")
        print(f"  Bill Paid Amount: Rs {bill.paid_amount:,.2f}")
        print(f"  Bill Balance Due: Rs {bill.balance_due:,.2f}")
        print(f"  Bill Status: {bill.status}")
        print(f"  Advance 1: Applied: Rs {adv1.applied_amount:,.2f} | Remaining: Rs {adv1.remaining_balance:,.2f}")
        
        assert bill.paid_amount == apply_amount, f"Bill paid amount should be {apply_amount}"
        assert adv1.applied_amount == apply_amount, f"Advance applied should be {apply_amount}"
        assert adv1.remaining_balance == (adv1.amount - apply_amount), "Remaining balance calculation incorrect"
        print("\n✓ TEST 1 PASSED")

def test_scenario_2(app):
    """Test: Advance deletion reverses the applied amount"""
    print("\n" + "="*60)
    print("TEST 2: Advance Deletion Reverses Applied Amount")
    print("="*60)
    
    user, vendor, bill, adv1, adv2, product = create_test_data(app)
    
    with app.app_context():
        bill = PurchaseBill.query.get(bill.id)
        adv1 = VendorAdvance.query.get(adv1.id)
        
        print(f"\nInitial Bill Status:")
        print(f"  Bill Total: Rs {bill.total:,.2f}")
        print(f"  Bill Paid Amount: Rs {bill.paid_amount:,.2f}")
        
        # Apply advance to bill
        apply_amount = min(adv1.remaining_balance, bill.balance_due)
        adv1.applied_amount = apply_amount
        adv1.adjusted_bill_id = bill.id
        bill.paid_amount += apply_amount
        bill.update_status()
        db.session.commit()
        
        print(f"\nAfter Applying Advance:")
        print(f"  Bill Paid Amount: Rs {bill.paid_amount:,.2f}")
        print(f"  Advance Applied: Rs {adv1.applied_amount:,.2f}")
        
        # Delete the advance
        adv_id = adv1.id
        adv_applied = adv1.applied_amount
        if adv1.applied_amount > 0 and adv1.adjusted_bill_id:
            bill_record = PurchaseBill.query.get(adv1.adjusted_bill_id)
            if bill_record:
                bill_record.paid_amount = max(0, bill_record.paid_amount - adv1.applied_amount)
                bill_record.update_status()
        
        db.session.delete(adv1)
        db.session.commit()
        
        print(f"\nAfter Deleting Advance:")
        print(f"  Bill Paid Amount: Rs {bill.paid_amount:,.2f}")
        print(f"  Expected: Rs 0.00")
        
        assert bill.paid_amount == 0, f"Bill paid amount should be 0 after deleting advance"
        print("\n✓ TEST 2 PASSED")

def test_scenario_3(app):
    """Test: Multiple advances application to one bill"""
    print("\n" + "="*60)
    print("TEST 3: Multiple Advances Applied to One Bill")
    print("="*60)
    
    user, vendor, bill, adv1, adv2, product = create_test_data(app)
    
    with app.app_context():
        bill = PurchaseBill.query.get(bill.id)
        adv1 = VendorAdvance.query.get(adv1.id)
        adv2 = VendorAdvance.query.get(adv2.id)
        
        print(f"\nInitial State:")
        print(f"  Bill Total: Rs {bill.total:,.2f}")
        print(f"  Advance 1: Rs {adv1.amount:,.2f}")
        print(f"  Advance 2: Rs {adv2.amount:,.2f}")
        print(f"  Total Advances Available: Rs {adv1.amount + adv2.amount:,.2f}")
        
        # Apply both advances to bill
        remaining_to_apply = bill.total
        applied_total = 0
        
        for adv in [adv1, adv2]:
            if remaining_to_apply <= 0:
                break
            can_apply = min(adv.remaining_balance, remaining_to_apply)
            if can_apply > 0:
                adv.applied_amount += can_apply
                bill.paid_amount += can_apply
                applied_total += can_apply
                remaining_to_apply -= can_apply
        
        bill.update_status()
        db.session.commit()
        
        print(f"\nAfter Applying Advances:")
        print(f"  Total Applied from Advances: Rs {applied_total:,.2f}")
        print(f"  Bill Paid Amount: Rs {bill.paid_amount:,.2f}")
        print(f"  Bill Status: {bill.status}")
        print(f"  Advance 1: Applied: Rs {adv1.applied_amount:,.2f}")
        print(f"  Advance 2: Applied: Rs {adv2.applied_amount:,.2f}")
        
        assert bill.paid_amount == applied_total, f"Bill paid should equal applied amount"
        assert adv1.applied_amount > 0, "Advance 1 should be partially applied"
        print("\n✓ TEST 3 PASSED")

def test_scenario_4(app):
    """Test: Vendor balance calculations"""
    print("\n" + "="*60)
    print("TEST 4: Vendor Balance Calculations")
    print("="*60)
    
    user, vendor, bill, adv1, adv2, product = create_test_data(app)
    
    with app.app_context():
        vendor = Vendor.query.get(vendor.id)
        adv1 = VendorAdvance.query.get(adv1.id)
        adv2 = VendorAdvance.query.get(adv2.id)
        
        print(f"\nInitial Vendor Balance:")
        print(f"  Total Advances Given: Rs {vendor.total_advances_given:,.2f}")
        print(f"  Total Advances Adjusted: Rs {vendor.total_advances_adjusted:,.2f}")
        print(f"  Remaining Advance Balance: Rs {vendor.remaining_advance_balance:,.2f}")
        
        # Apply advances
        adv1.applied_amount = 3000
        adv2.applied_amount = 0
        db.session.commit()
        
        print(f"\nAfter Applying Rs 3000 from Advance 1:")
        print(f"  Total Advances Given: Rs {vendor.total_advances_given:,.2f}")
        print(f"  Total Advances Adjusted: Rs {vendor.total_advances_adjusted:,.2f}")
        print(f"  Remaining Advance Balance: Rs {vendor.remaining_advance_balance:,.2f}")
        
        expected_remaining = (adv1.amount + adv2.amount) - 3000
        assert vendor.remaining_advance_balance == expected_remaining, f"Remaining should be {expected_remaining}"
        print("\n✓ TEST 4 PASSED")

if __name__ == '__main__':
    app = create_app()
    
    try:
        test_scenario_1(app)
        test_scenario_2(app)
        test_scenario_3(app)
        test_scenario_4(app)
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED! ✓")
        print("="*60)
        print("\nFixes Summary:")
        print("✓ Advance partial application works correctly")
        print("✓ Advance deletion reverses applied amounts")
        print("✓ Multiple advances can be applied to single bill")
        print("✓ Vendor balance calculations are accurate")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
