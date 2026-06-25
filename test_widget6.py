import sys
sys.path.insert(0, '.')
from app import create_app
from app import db
from app.models import User
from flask import render_template_string
from datetime import datetime

app = create_app()
app.config['TESTING'] = True

with app.app_context():
    # Create admin user
    admin = User(username='testadmin', email='test@test.com', role='admin', is_active=True)
    admin.set_password('test123')
    db.session.add(admin)
    db.session.commit()
    
    # Simulate being logged in as admin
    from flask_login import login_user
    login_user(admin)
    
    # Create a simple widget template inline
    test_template = """
    {% from 'components/approval_widget.html' import approval_widget %}
    {% set ns = namespace(foo=None) %}
    {% set ns.foo = approval_service.get_config('expense') %}
    config exists: {{ ns.foo is not none }}
    """
    
    class MockExpense:
        id = 1
        status = 'pending'
        is_approved = False
        is_rejected = False
        rejection_reason = ''
    
    try:
        html = render_template_string(test_template)
        print('Inline template:', html[:200])
    except Exception as e:
        print(f'Inline template error: {e}')
    
    # Now test the actual macro with a real template
    test_template2 = """
    {% from 'components/approval_widget.html' import approval_widget %}
    {{ approval_widget(module='expense', entity=exp) }}
    """
    
    mock_exp = MockExpense()
    try:
        html2 = render_template_string(test_template2, exp=mock_exp)
        print('Widget macro output:', html2[:300])
    except Exception as e:
        print(f'Widget macro error: {e}')
