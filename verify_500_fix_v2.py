from app import create_app, db
from app.models import Expense, SalaryPayment, SalaryAdvance, Staff
from datetime import datetime, date

app = create_app()
with app.app_context():
    try:
        # Get one of each
        e_obj = Expense.query.first()
        p_obj = SalaryPayment.query.first()
        a_obj = SalaryAdvance.query.first()
        
        unified = []
        if e_obj: unified.append({'date': e_obj.date})
        if p_obj: unified.append({'date': p_obj.payment_date})
        if a_obj: unified.append({'date': a_obj.date})
        
        print(f"Items in unified: {len(unified)}")
        for i, item in enumerate(unified):
            print(f"Item {i} date type: {type(item['date'])}")
            
        if len(unified) > 1:
            # Test the exact logic from reports.py
            unified.sort(key=lambda x: x['date'].date() if hasattr(x['date'], 'date') else x['date'], reverse=True)
            print("Sorting successful!")
        
        # Test Query with Join
        search = "a" # common letter
        q = SalaryPayment.query.join(Staff).filter(Staff.name.ilike(f'%{search}%'))
        res = q.all()
        print(f"Query successful: {len(res)} results")
        
        print("Final Verification: PASSED")
    except Exception as e:
        print(f"Final Verification: FAILED - {e}")
        import traceback
        traceback.print_exc()
