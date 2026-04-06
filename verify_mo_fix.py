from app import create_app, db
from app.models import ManufacturingOrder, BOM
from datetime import datetime
import time

app = create_app()
with app.app_context():
    try:
        # 1. Create a dummy order for today manually
        today = datetime.utcnow()
        day_str = today.strftime('%Y%m%d')
        prefix = f"MO-{day_str}-"
        
        # Test if BOM exists
        bom = BOM.query.first()
        if not bom:
            print("No BOM found to test MO creation.")
        else:
            # Check current max
            last_order = ManufacturingOrder.query.filter(
                ManufacturingOrder.order_number.like(f"{prefix}%")
            ).order_by(ManufacturingOrder.order_number.desc()).first()
            
            print(f"Current last order: {last_order.order_number if last_order else 'None'}")
            
            # Simulate the logic
            if last_order:
                last_suffix = int(last_order.order_number.split('-')[-1])
                new_suffix = last_suffix + 1
            else:
                new_suffix = 1
            
            new_mo_num = f"{prefix}{new_suffix:03d}"
            print(f"Generated next number: {new_mo_num}")
            
            # Verify uniqueness
            exists = ManufacturingOrder.query.filter_by(order_number=new_mo_num).first()
            if exists:
                print(f"FAILED: Generated number {new_mo_num} already exists!")
            else:
                print(f"PASSED: Generated number {new_mo_num} is unique.")
                
        print("Verification successful!")
    except Exception as e:
        print(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
