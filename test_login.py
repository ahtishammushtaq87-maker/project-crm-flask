"""
Test the login functionality
"""
from app import create_app
from app.models import User

app = create_app()

with app.test_client() as client:
    # Test login with correct password
    response = client.post('/login', data={
        'username': 'ahtisham',
        'password': 'password123'
    }, follow_redirects=True)
    
    print(f"Login attempt status: {response.status_code}")
    
    if response.status_code == 200:
        if b'Invalid username or password' in response.data:
            print("✗ Login FAILED - Invalid credentials message shown")
        elif b'Dashboard' in response.data or b'dashboard' in response.data.lower():
            print("✓ Login SUCCESSFUL - User logged in")
        else:
            print("? Login response unclear - checking response content")
            # print first 500 chars
            print(response.data[:500].decode('utf-8', errors='ignore'))
    else:
        print(f"✗ Login failed with status code {response.status_code}")
