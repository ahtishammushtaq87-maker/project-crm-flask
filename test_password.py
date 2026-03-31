from app import db, create_app
from app.models import User
from werkzeug.security import generate_password_hash, check_password_hash

app = create_app()
with app.app_context():
    # Test password hashing
    test_password = 'password123'
    empty_password = ''
    
    hash1 = generate_password_hash(test_password)
    hash2 = generate_password_hash(empty_password)
    
    print('Testing password hashing:')
    print(f'Valid password hash correct: {check_password_hash(hash1, test_password)}')
    print(f'Empty password hash correct: {check_password_hash(hash2, "")}')
    print(f'Empty password vs password123: {check_password_hash(hash2, "password123")}')
    print()
    
    # Check if there's a staff user with empty password
    staff_users = User.query.filter_by(role='user').all()
    print(f'Found {len(staff_users)} staff users')
    for user in staff_users:
        print(f'  - {user.username}: password_hash starts with {user.password_hash[:20]}...')
        # Try to verify with 'password123'
        can_login = check_password_hash(user.password_hash, 'password123')
        print(f'    Can login with password123: {can_login}')
