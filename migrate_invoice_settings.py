from app import db
from app.models import InvoiceSettings

def migrate_invoice_settings():
    """Add new columns to invoice_settings table"""
    
    # Check if columns exist by trying to add them
    try:
        # Add columns one by one using raw SQL
        db.session.execute(db.text("ALTER TABLE invoice_settings ADD COLUMN invoice_prefix VARCHAR(10)"))
        db.session.execute(db.text("ALTER TABLE invoice_settings ADD COLUMN invoice_suffix VARCHAR(10)"))
        db.session.execute(db.text("ALTER TABLE invoice_settings ADD COLUMN next_number INTEGER DEFAULT 1"))
        db.session.execute(db.text("ALTER TABLE invoice_settings ADD COLUMN tax_name VARCHAR(50)"))
        db.session.execute(db.text("ALTER TABLE invoice_settings ADD COLUMN tax_rate NUMERIC(10, 2) DEFAULT 10"))
        db.session.execute(db.text("ALTER TABLE invoice_settings ADD COLUMN payment_terms TEXT"))
        db.session.execute(db.text("ALTER TABLE invoice_settings ADD COLUMN notes TEXT"))
        db.session.commit()
        print("Migration successful!")
    except Exception as e:
        print(f"Migration error (may already exist): {e}")
        db.session.rollback()

if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        migrate_invoice_settings()