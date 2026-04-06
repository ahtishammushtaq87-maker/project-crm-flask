import sys
import os

# Redirect stdout to a file for better reading
sys.stdout = open('diagnostic_result.txt', 'w')

from app import create_app, db
from app.models import MonthlyTarget, ManufacturingOrder, Sale, SaleItem
from datetime import datetime

app = create_app()
with app.app_context():
    print("--- Diagnostic Report ---")
    targets = MonthlyTarget.query.all()
    print(f"Total Monthly Targets found: {len(targets)}")
    for t in targets:
        print(f"Target record for {t.month}/{t.year}: ProdQty={t.target_production_qty}, SalesRev={t.target_sales_revenue}")
        
    mo_count = ManufacturingOrder.query.count()
    comp_mo_count = ManufacturingOrder.query.filter_by(status='Completed').count()
    print(f"Total MOs: {mo_count}, Completed MOs: {comp_mo_count}")
    
    if comp_mo_count > 0:
        recent_mo = ManufacturingOrder.query.filter_by(status='Completed').order_by(ManufacturingOrder.end_date.desc()).first()
        print(f"Most recent completed MO: {recent_mo.order_number}, End Date: {recent_mo.end_date}, Status: {recent_mo.status}")
        
    sale_count = Sale.query.count()
    print(f"Total Sales: {sale_count}")
    
    if sale_count > 0:
        recent_sale = Sale.query.order_by(Sale.date.desc()).first()
        print(f"Most recent sale: {recent_sale.invoice_number}, Date: {recent_sale.date}, Total: {recent_sale.total}")
    
    # Try one manual query for April (Month 4)
    start_date = datetime(2026, 4, 1)
    end_date = datetime(2026, 5, 1)
    rev = db.session.query(db.func.sum(Sale.total)).filter(Sale.date >= start_date, Sale.date < end_date).scalar() or 0
    print(f"Manual Test for April 2026: Revenue calculated as {rev}")
        
    print("--- End Diagnostic ---")
