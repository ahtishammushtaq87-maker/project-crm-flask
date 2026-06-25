import sys
sys.path.insert(0, '.')
from app import create_app
app = create_app()
app.config['TESTING'] = True

with app.test_client() as client:
    resp = client.get('/auth/login')
    html = resp.data.decode()
    
    # Try login
    resp = client.post('/auth/login', data={
        'username': 'admin',
        'password': 'admin123',
        'submit': 'Login'
    }, follow_redirects=True)
    
    print(f'Final status: {resp.status_code}')
    html = resp.data.decode()
    
    # Check if we're on dashboard or still on login page
    if 'Login' in html and 'Password' in html:
        print('Still on login page!')
    elif 'Dashboard' in html or 'dashboard' in html.lower():
        print('On dashboard page')
    else:
        print(f'On unknown page, length: {len(html)}')
        print('First 500 chars:', html[:500])
    
    # Now try invoices
    resp2 = client.get('/sales/invoices')
    print(f'Invoices status: {resp2.status_code}')
    print(f'Invoices location: {resp2.headers.get("Location", "none")}')
    
    html2 = resp2.data.decode()
    if 'approval-widget' in html2:
        print('Widget found!')
    else:
        print('No widget in invoices')
        # Count occurrences of 'badge' to see if page has any badges
        print(f'Badge count: {html2.count("badge")}')
