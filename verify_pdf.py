import sys
import os

# Add the project directory to path
sys.path.append(os.getcwd())

from flask import Flask
from app import db
from app.models import Sale, PurchaseBill, Company, InvoiceSettings, Customer, Vendor, Product, SaleItem, PurchaseItem
from app.pdf_utils import generate_professional_pdf
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db.init_app(app)

def verify_pdfs():
    with app.app_context():
        # Get existing data or create mock if needed
        sale = Sale.query.first()
        bill = PurchaseBill.query.first()
        company = Company.query.first()
        settings = InvoiceSettings.query.first()
        
        print(f"Testing Sales Invoice PDF generation for {sale.invoice_number if sale else 'N/A'}...")
        if sale:
            try:
                buffer = generate_professional_pdf('invoice', sale, company, settings)
                with open('test_invoice.pdf', 'wb') as f:
                    f.write(buffer.getvalue())
                print("✓ Sales Invoice PDF generated successfully: test_invoice.pdf")
            except Exception as e:
                print(f"✗ Sales Invoice PDF generation failed: {str(e)}")
        else:
            print("! No sale found in DB to test.")

        print(f"\nTesting Purchase Bill PDF generation for {bill.bill_number if bill else 'N/A'}...")
        if bill:
            try:
                buffer = generate_professional_pdf('purchase', bill, company)
                with open('test_purchase.pdf', 'wb') as f:
                    f.write(buffer.getvalue())
                print("✓ Purchase Bill PDF generated successfully: test_purchase.pdf")
            except Exception as e:
                print(f"✗ Purchase Bill PDF generation failed: {str(e)}")
        else:
            print("! No purchase bill found in DB to test.")

if __name__ == "__main__":
    verify_pdfs()
