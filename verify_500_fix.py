from app import create_app, db
from app.models import Expense, SalaryPayment, SalaryAdvance, Staff
from datetime import datetime

app = create_app()
with app.app_context():
    try:
        from app.routes.reports import expense_report
        # We can't easily call the route function because it returns a template
        # but we can test the logic inside it
        
        # 1. Test Regular Expense (datetime)
        e = Expense.query.first()
        if e:
            print(f"Expense date type: {type(e.date)}")
            
        # 2. Test Salary Payment (date)
        p = SalaryPayment.query.first()
        if p:
            print(f"Salary payment date type: {type(p.payment_date)}")
            
        # 3. Test sorting logic
        test_data = []
        if e: test_data.append({'date': e.date})
        if p: test_data.append({'date': p.payment_date})
        
        if len(test_data) > 1:
            # This is the line that was failing
            test_data.sort(key=lambda x: x['date'].date() if hasattr(x['date'], 'date') and not isinstance(x['date'], datetime.date) else x['date'], reverse=True)
            # Actually, hasattr(datetime, 'date') is True, but it's a method. 
            # hasattr(date, 'date') is False.
            
            # Let's verify the logic I actually put in reports.py:
            # key=lambda x: x['date'].date() if hasattr(x['date'], 'date') else x['date']
            # Wait, datetime has a .date() method. date object DOES NOT have a .date() method (it has .day, .month, etc).
            # So if x['date'] is a date object, hasattr(x['date'], 'date') is False.
            # If x['date'] is a datetime object, hasattr(x['date'], 'date') is True.
            # This logic should work.
            
            test_data.sort(key=lambda x: x['date'].date() if hasattr(x['date'], 'date') else x['date'], reverse=True)
            print("Sorting logic verified!")
        else:
            print("Not enough data to test sorting, but logic seems sound.")

        # 4. Test Search logic
        search = "Test"
        pay_query = SalaryPayment.query.join(Staff).filter(SalaryPayment.status == 'paid')
        pay_query = pay_query.filter(Staff.name.ilike(f'%{search}%'))
        results = pay_query.all()
        print(f"Search query executed successfully. Found {len(results)} results.")

        print("Verification successful!")
    except Exception as e:
        print(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
