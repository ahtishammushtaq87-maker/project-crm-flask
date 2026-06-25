import sys
sys.path.insert(0, '.')
from app import create_app
app = create_app()
app.config['TESTING'] = True

with app.test_client() as client:
    client.get('/auth/login')
    
    resp = client.post('/auth/login', data={
        'username': 'admin',
        'password': 'admin123',
        'csrf_token': 'test'
    }, follow_redirects=True)
    print(f'Login status: {resp.status_code}')
    
    resp = client.get('/sales/invoices')
    print(f'Invoices: {resp.status_code}, has widget: {b"approval-widget" in resp.data}')
    
    resp = client.get('/accounting/expenses')
    print(f'Expenses: {resp.status_code}, has widget: {b"approval-widget" in resp.data}')
    
    resp = client.get('/purchase/bills')
    print(f'Bills: {resp.status_code}, has widget: {b"approval-widget" in resp.data}')
