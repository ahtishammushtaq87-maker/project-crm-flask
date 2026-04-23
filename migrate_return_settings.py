"""
Migration script to create SaleReturnSettings and PurchaseReturnSettings tables.
Run this script to create the new tables for return number settings.
"""

from app import db, create_app
from app.models import SaleReturnSettings, PurchaseReturnSettings

def migrate():
    app = create_app()
    with app.app_context():
        print("Creating return settings tables...")
        
        # Create tables if they don't exist
        db.create_all()
        
        # Check if settings exist, create defaults if not
        sale_settings = SaleReturnSettings.query.first()
        if not sale_settings:
            print("Creating default SaleReturnSettings...")
            sale_settings = SaleReturnSettings(
                return_prefix='RET-',
                return_suffix='',
                next_number=1
            )
            db.session.add(sale_settings)
        
        purchase_settings = PurchaseReturnSettings.query.first()
        if not purchase_settings:
            print("Creating default PurchaseReturnSettings...")
            purchase_settings = PurchaseReturnSettings(
                return_prefix='PRet-',
                return_suffix='',
                next_number=1
            )
            db.session.add(purchase_settings)
        
        db.session.commit()
        print("✅ Return settings migration completed successfully!")

if __name__ == '__main__':
    migrate()
