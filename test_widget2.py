import sys
sys.path.insert(0, '.')
from app import create_app
app = create_app()
app.config['TESTING'] = True

with app.test_client() as client:
    # GET login page to get CSRF token
    resp = client.get('/auth/login')
    html = resp.data.decode()
    
    # Check if login page loaded
    if 'Login' in html or 'login' in html.lower():
        print('Login page loaded OK')
    else:
        print('Login page may have failed')
    
    # Try login
    resp = client.post('/auth/login', data={
        'username': 'admin',
        'password': 'admin123',
        'submit': 'Login'
    }, follow_redirects=False)
    print(f'Login POST: {resp.status_code}')
    print(f'Login location: {resp.headers.get("Location", "none")}')
    
    # Follow redirect to see where we land
    resp2 = client.get(resp.headers.get('Location', '/'), follow_redirects=True)
    print(f'After login: {resp2.status_code}')
    html2 = resp2.data.decode()
    
    # Check if we're logged in by looking for user info or dashboard content
    if 'Dashboard' in html2 or 'dashboard' in html2.lower():
        print('Looks like we reached dashboard')
    elif 'Login' in html2:
        print('Still on login page - login failed')
    
    # Check for widget HTML in the response
    if 'approval-widget' in html2:
        print('SUCCESS: Widget found in page!')
    else:
        print('No widget in page')
    
    # Try direct GET to invoices
    resp3 = client.get('/sales/invoices')
    print(f'Invoices direct GET: {resp3.status_code}, location: {resp3.headers.get("Location", "none")}')
