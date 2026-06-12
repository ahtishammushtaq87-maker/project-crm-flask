from run import app, db
from app.models import Sale

with app.app_context():
    sales = Sale.query.filter_by(is_approved=False).all()
    count = 0
    for s in sales:
        s.calculate_totals()
        count += 1
    db.session.commit()
    print(f'Recalculated {count} unapproved invoices')
