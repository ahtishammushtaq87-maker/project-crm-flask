import sys
sys.path.insert(0, '.')
from app import create_app
app = create_app()
app.config['TESTING'] = True

with app.test_client() as client:
    resp = client.get('/auth/login')
    
    # Try login
    resp = client.post('/auth/login', data={
        'username': 'admin',
        'password': 'admin123',
        'submit': 'Login'
    }, follow_redirects=True)
    
    # Check invoices
    resp = client.get('/sales/invoices', follow_redirects=True)
    html = resp.data.decode()
    
    # Search for widget HTML
    if 'approval-widget' in html:
        print('SUCCESS: Widget HTML found in invoices page!')
        # Show a snippet around the widget
        idx = html.find('approval-widget')
        print('Snippet:', html[idx:idx+200])
    else:
        print('FAIL: Widget HTML NOT found in invoices page')
        # Check for errors
        if '500' in str(resp.status_code) or 'error' in html.lower():
            print('Page may have errors')
    
    # Check expenses
    resp = client.get('/accounting/expenses', follow_redirects=True)
    html = resp.data.decode()
    if 'approval-widget' in html:
        print('SUCCESS: Widget HTML found in expenses page!')
    else:
        print('FAIL: Widget HTML NOT found in expenses page')
