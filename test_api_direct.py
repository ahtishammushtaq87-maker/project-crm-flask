#!/usr/bin/env python
from app import create_app
import json

app = create_app()

# Test the API with proper authentication
with app.app_context():
    from app.models import User
    user = User.query.first()
    
    if not user:
        print("No users found")
    else:
        print(f"Testing with user: {user.username}")
        
        with app.test_request_context():
            from flask_login import login_user
            login_user(user, remember=False)
            
            # Now test the API endpoint
            with app.test_client() as client:
                # Manually set up the session
                response = client.get('/purchase/api/vendor/1/advances')
                print(f"Status: {response.status_code}")
                print(f"Response: {json.dumps(response.get_json(), indent=2)}")
