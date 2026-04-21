from app import create_app, db
from app.models import PaymentMethod

app = create_app()
with app.app_context():
    db.create_all()
    methods = PaymentMethod.query.all()
    if not methods:
        db.session.add(PaymentMethod(name='Cash', description='Cash payment'))
        db.session.add(PaymentMethod(name='Bank Transfer', description='Direct bank transfer or online payment'))
        db.session.add(PaymentMethod(name='Cheque', description='Payment via Cheque'))
        db.session.commit()
        print('Seeded payment methods!')
    else:
        print('Payment methods already exist.')
