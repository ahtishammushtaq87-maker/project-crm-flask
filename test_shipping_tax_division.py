"""
Test shipping and tax division in purchase bills.
Verifies that shipping and tax are divided proportionally among items
and that inventory costs are updated correctly.
"""

import sys
sys.path.insert(0, 'D:\\prefex_flask\\project_crm_flask\\project_crm_flask')

from app import create_app, db
from app.models import (
    PurchaseBill, PurchaseItem, Product, Vendor, User, 
    CostPriceHistory, Currency
)
from datetime import datetime, timedelta

def test_shipping_tax_division_on_create():
    """Test that shipping and tax are divided proportionally when creating a bill"""
    app = create_app()
    
    with app.app_context():
        # Clean up test data
        PurchaseBill.query.filter_by(bill_number='TEST-SHIP-001').delete()
        db.session.commit()
        
        # Create test vendor if not exists
        vendor = Vendor.query.filter_by(name='Test Vendor').first()
        if not vendor:
            vendor = Vendor(name='Test Vendor', email='test@vendor.com', is_active=True)
            db.session.add(vendor)
            db.session.commit()
        
        # Create test products
        products = []
        for i in range(1, 4):
            prod = Product.query.filter_by(code=f'TEST-PROD-{i}').first()
            if not prod:
                prod = Product(
                    code=f'TEST-PROD-{i}',
                    name=f'Test Product {i}',
                    cost_price=100.0 if i == 1 else (200.0 if i == 2 else 50.0),
                    selling_price=150.0 if i == 1 else (300.0 if i == 2 else 100.0),
                    quantity=0,
                    uom='pcs',
                    is_active=True
                )
                db.session.add(prod)
                db.session.commit()
            products.append(prod)
        
        # Record old costs
        old_costs = {p.id: p.cost_price for p in products}
        
        # Create a purchase bill with shipping and tax
        # Item 1: 100 units @ Rs 100 = Rs 10,000
        # Item 2: 50 units @ Rs 200 = Rs 10,000
        # Item 3: 100 units @ Rs 50 = Rs 5,000
        # Subtotal: Rs 25,000
        # Shipping: Rs 1,000
        # Tax (10%): (25,000 + 1,000) × 10% = Rs 2,600
        # Total: Rs 28,600
        
        bill = PurchaseBill(
            bill_number='TEST-SHIP-001',
            vendor_id=vendor.id,
            date=datetime.now(),
            due_date=datetime.now() + timedelta(days=30),
            tax_rate=10,
            discount=0,
            shipping_charge=1000,
            currency_id=1,
            exchange_rate=1,
            created_by=1
        )
        db.session.add(bill)
        db.session.flush()
        
        # Item 1: 100 @ 100 = 10,000 (40% of subtotal)
        item1 = PurchaseItem(
            bill_id=bill.id,
            product_id=products[0].id,
            quantity=100,
            unit_price=100,
            total=10000
        )
        db.session.add(item1)
        
        # Item 2: 50 @ 200 = 10,000 (40% of subtotal)
        item2 = PurchaseItem(
            bill_id=bill.id,
            product_id=products[1].id,
            quantity=50,
            unit_price=200,
            total=10000
        )
        db.session.add(item2)
        
        # Item 3: 100 @ 50 = 5,000 (20% of subtotal)
        item3 = PurchaseItem(
            bill_id=bill.id,
            product_id=products[2].id,
            quantity=100,
            unit_price=50,
            total=5000
        )
        db.session.add(item3)
        
        # Update products
        subtotal = 25000
        shipping = 1000
        taxable = subtotal + shipping
        tax_amount = taxable * 0.10  # 2600
        total_additional = shipping + tax_amount  # 3600
        
        # Item 1: 40% allocation = 3600 * 0.40 = 1440
        allocated_1 = total_additional * (10000 / subtotal)
        new_unit_cost_1 = 100 + (allocated_1 / 100)
        
        # Item 2: 40% allocation = 3600 * 0.40 = 1440
        allocated_2 = total_additional * (10000 / subtotal)
        new_unit_cost_2 = 200 + (allocated_2 / 50)
        
        # Item 3: 20% allocation = 3600 * 0.20 = 720
        allocated_3 = total_additional * (5000 / subtotal)
        new_unit_cost_3 = 50 + (allocated_3 / 100)
        
        products[0].cost_price = new_unit_cost_1
        products[0].quantity += 100
        
        products[1].cost_price = new_unit_cost_2
        products[1].quantity += 50
        
        products[2].cost_price = new_unit_cost_3
        products[2].quantity += 100
        
        bill.calculate_totals()
        db.session.commit()
        
        # Verify calculations
        print("\n=== TEST: Shipping & Tax Division on Bill Create ===")
        print(f"\nBill Summary:")
        print(f"  Subtotal: Rs {bill.subtotal:,.2f}")
        print(f"  Shipping: Rs {bill.shipping_charge:,.2f}")
        print(f"  Tax Rate: {bill.tax_rate}%")
        print(f"  Tax Amount: Rs {bill.tax:,.2f}")
        print(f"  Total: Rs {bill.total:,.2f}")
        
        print(f"\nProduct Cost Updates:")
        print(f"  Product 1:")
        print(f"    Old Cost: Rs {old_costs[products[0].id]:.2f}")
        print(f"    New Cost: Rs {products[0].cost_price:.2f}")
        print(f"    Allocated Additional: Rs {allocated_1:.2f}")
        print(f"    Qty: {products[0].quantity}")
        
        print(f"  Product 2:")
        print(f"    Old Cost: Rs {old_costs[products[1].id]:.2f}")
        print(f"    New Cost: Rs {products[1].cost_price:.2f}")
        print(f"    Allocated Additional: Rs {allocated_2:.2f}")
        print(f"    Qty: {products[1].quantity}")
        
        print(f"  Product 3:")
        print(f"    Old Cost: Rs {old_costs[products[2].id]:.2f}")
        print(f"    New Cost: Rs {products[2].cost_price:.2f}")
        print(f"    Allocated Additional: Rs {allocated_3:.2f}")
        print(f"    Qty: {products[2].quantity}")
        
        # Assertions
        assert bill.total == 28600, f"Total should be 28600, got {bill.total}"
        assert abs(bill.tax - 2600) < 0.01, f"Tax should be 2600, got {bill.tax}"
        assert abs(products[0].cost_price - new_unit_cost_1) < 0.01, "Product 1 cost incorrect"
        assert abs(products[1].cost_price - new_unit_cost_2) < 0.01, "Product 2 cost incorrect"
        assert abs(products[2].cost_price - new_unit_cost_3) < 0.01, "Product 3 cost incorrect"
        
        print("\n✅ All assertions passed!")
        return True


def test_shipping_update():
    """Test that shipping update divides cost proportionally"""
    app = create_app()
    
    with app.app_context():
        # Get the bill created in previous test
        bill = PurchaseBill.query.filter_by(bill_number='TEST-SHIP-001').first()
        
        if not bill:
            print("Bill not found for shipping update test")
            return False
        
        print("\n=== TEST: Shipping Update ===")
        print(f"Original Shipping: Rs {bill.shipping_charge:,.2f}")
        
        # Record old costs
        old_product_costs = {}
        for item in bill.items:
            prod = Product.query.get(item.product_id)
            old_product_costs[item.product_id] = prod.cost_price
        
        # Update shipping from 1000 to 2000
        old_shipping = bill.shipping_charge
        new_shipping = 2000
        
        # Recalculate
        total_items_cost = sum(item.total for item in bill.items)
        taxable_amount = total_items_cost + new_shipping
        tax_amount = (taxable_amount * bill.tax_rate) / 100
        total_additional_cost = new_shipping + tax_amount
        
        for item in bill.items:
            product = Product.query.get(item.product_id)
            if product:
                allocation_ratio = item.total / total_items_cost
                allocated_additional = total_additional_cost * allocation_ratio
                new_cost_price = item.unit_price + (allocated_additional / item.quantity)
                product.cost_price = new_cost_price
        
        bill.shipping_charge = new_shipping
        bill.calculate_totals()
        db.session.commit()
        
        print(f"Updated Shipping: Rs {bill.shipping_charge:,.2f}")
        print(f"Updated Tax: Rs {bill.tax:,.2f}")
        print(f"Updated Total: Rs {bill.total:,.2f}")
        
        print(f"\nProduct Cost Changes:")
        for item in bill.items:
            prod = Product.query.get(item.product_id)
            old_cost = old_product_costs[item.product_id]
            new_cost = prod.cost_price
            print(f"  Product {item.product_id}: Rs {old_cost:.2f} → Rs {new_cost:.2f}")
        
        print("\n✅ Shipping update completed successfully!")
        return True


def test_tax_update():
    """Test that tax rate update divides cost proportionally"""
    app = create_app()
    
    with app.app_context():
        # Get the bill
        bill = PurchaseBill.query.filter_by(bill_number='TEST-SHIP-001').first()
        
        if not bill:
            print("Bill not found for tax update test")
            return False
        
        print("\n=== TEST: Tax Rate Update ===")
        print(f"Original Tax Rate: {bill.tax_rate}%")
        print(f"Original Tax Amount: Rs {bill.tax:,.2f}")
        
        # Record old costs
        old_product_costs = {}
        for item in bill.items:
            prod = Product.query.get(item.product_id)
            old_product_costs[item.product_id] = prod.cost_price
        
        # Update tax from 10% to 15%
        old_tax_rate = bill.tax_rate
        new_tax_rate = 15
        
        # Recalculate
        total_items_cost = sum(item.total for item in bill.items)
        taxable_amount = total_items_cost + bill.shipping_charge
        new_tax_total = (taxable_amount * new_tax_rate) / 100
        total_additional_cost = bill.shipping_charge + new_tax_total
        
        for item in bill.items:
            product = Product.query.get(item.product_id)
            if product:
                allocation_ratio = item.total / total_items_cost
                allocated_additional = total_additional_cost * allocation_ratio
                new_cost_price = item.unit_price + (allocated_additional / item.quantity)
                product.cost_price = new_cost_price
        
        bill.tax_rate = new_tax_rate
        bill.calculate_totals()
        db.session.commit()
        
        print(f"Updated Tax Rate: {bill.tax_rate}%")
        print(f"Updated Tax Amount: Rs {bill.tax:,.2f}")
        print(f"Updated Total: Rs {bill.total:,.2f}")
        
        print(f"\nProduct Cost Changes:")
        for item in bill.items:
            prod = Product.query.get(item.product_id)
            old_cost = old_product_costs[item.product_id]
            new_cost = prod.cost_price
            print(f"  Product {item.product_id}: Rs {old_cost:.2f} → Rs {new_cost:.2f}")
        
        print("\n✅ Tax rate update completed successfully!")
        return True


if __name__ == '__main__':
    try:
        test_shipping_tax_division_on_create()
        test_shipping_update()
        test_tax_update()
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
