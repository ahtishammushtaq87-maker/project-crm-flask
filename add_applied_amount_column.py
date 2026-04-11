"""
Migration script to add applied_amount column to vendor_advances table
This allows tracking partial advance applications to bills
"""
from app import db, create_app
from app.models import VendorAdvance
from sqlalchemy import text

def migrate():
    app = create_app()
    with app.app_context():
        try:
            # Check if column already exists
            inspector = db.inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('vendor_advances')]
            
            if 'applied_amount' not in columns:
                # Add the applied_amount column
                with db.engine.connect() as connection:
                    connection.execute(text(
                        'ALTER TABLE vendor_advances ADD COLUMN applied_amount FLOAT DEFAULT 0'
                    ))
                    connection.commit()
                print("✓ Successfully added 'applied_amount' column to vendor_advances table")
                print("✓ All existing advances will have applied_amount = 0 by default")
                print("✓ For adjusted advances, applied_amount will equal the full amount")
            else:
                print("✓ Column 'applied_amount' already exists")
            
            # Update existing adjusted advances to have applied_amount = amount
            adjusted_advances = VendorAdvance.query.filter(
                VendorAdvance.is_adjusted == True,
                VendorAdvance.applied_amount == 0
            ).all()
            
            for adv in adjusted_advances:
                adv.applied_amount = adv.amount
            
            db.session.commit()
            print(f"✓ Updated {len(adjusted_advances)} existing adjusted advances")
            
        except Exception as e:
            print(f"✗ Error during migration: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate()
    print("\n✓ Migration completed successfully!")
