import sys
sys.path.insert(0, '.')
from app import create_app
from app.models import User, Expense
from app import db
from flask_login import login_user
import os
from datetime import datetime

os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'

app = create_app()
app.config['TESTING'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'

with app.app_context():
    # Create tables
    db.create_all()
    
    # Create admin user
    admin = User(username='testadmin', email='test@test.com', role='admin', is_active=True)
    admin.set_password('test123')
    db.session.add(admin)
    
    # Create a pending expense
    from app.models import ExpenseCategory, Vendor
    cat = ExpenseCategory(name='Test Cat')
    db.session.add(cat)
    db.session.flush()
    
    exp = Expense(
        expense_number='TEST-001',
        amount=100,
        date=datetime.now(),
        expense_category_id=cat.id,
        status='pending',
        is_approved=False,
        is_rejected=False
    )
    db.session.add(exp)
    db.session.commit()
    
    # Login
    login_user(admin)
    
    # Render the expenses template directly
    from flask import render_template
    html = render_template('accounting/expenses.html', expenses=[exp], 
                          vendors=[], categories=[], manufacturing_orders=[],
                          selected_vendor=None, selected_category=None, selected_mo_id=None,
                          selected_start_date=None, selected_end_date=None,
                          total_expense=100, date_format='%Y-%m-%d')
    
    # Check for widget
    if 'approval-widget' in html:
        print('SUCCESS: Widget found in rendered template!')
        idx = html.find('approval-widget')
        print('Snippet:', html[idx:idx+300])
    else:
        print('FAIL: Widget NOT found')
        # Check if the macro import section is present
        if 'approval_widget' in html:
            print('But macro import IS present')
        else:
            print('Macro import NOT present either')
        
        # Check for errors
        if 'error' in html.lower() or 'exception' in html.lower():
            print('Template may have errors')
        print('HTML length:', len(html))
