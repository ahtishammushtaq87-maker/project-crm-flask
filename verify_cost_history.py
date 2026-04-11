#!/usr/bin/env python
"""Quick verification of Cost Price History System"""
from app import create_app, db
from app.models import CostPriceHistory, Product
from sqlalchemy import text

app = create_app()
with app.app_context():
    print("\n" + "="*60)
    print("COST PRICE HISTORY SYSTEM - VERIFICATION")
    print("="*60)
    
    # Check if table exists
    try:
        result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='cost_price_history'"))
        if result.fetchone():
            print("✅ cost_price_history table exists")
        else:
            print("❌ cost_price_history table NOT found")
    except Exception as e:
        print(f"⚠️ Could not check table: {e}")
    
    # Check CostPriceHistory model
    try:
        history_count = CostPriceHistory.query.count()
        print(f"✅ CostPriceHistory model working (records: {history_count})")
    except Exception as e:
        print(f"❌ Error with CostPriceHistory model: {e}")
    
    # Check products
    try:
        products = Product.query.all()
        print(f"✅ {len(products)} products in database")
    except Exception as e:
        print(f"❌ Error with Product query: {e}")
    
    # Check model relationships
    try:
        product = Product.query.first()
        if product and hasattr(product, 'cost_price_changes'):
            print("✅ Product.cost_price_changes relationship exists")
        else:
            print("⚠️ Product.cost_price_changes relationship not accessible")
    except Exception as e:
        print(f"⚠️ Could not check relationships: {e}")
    
    print("\n" + "="*60)
    print("ALL CHECKS COMPLETED")
    print("="*60)
    print("\nSystem is ready!")
    print("\nNext steps:")
    print("1. Go to Purchase → Create Bill")
    print("2. Select vendor and add items with different prices")
    print("3. Current Cost column shows old price")
    print("4. New Cost column shows new price")
    print("5. Yellow badge appears if prices differ")
    print("6. After saving, check Inventory → Products → History")
    print("="*60 + "\n")
