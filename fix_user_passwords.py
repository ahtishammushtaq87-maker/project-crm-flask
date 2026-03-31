"""
Fix users with bad (empty) passwords
"""
from app import db, create_app
from app.models import User

app = create_app()
with app.app_context():
    # Find all users and fix their passwords
    users = User.query.all()
    
    print(f"Checking {len(users)} users...")
    fixed_count = 0
    
    for user in users:
        # Try to verify with 'password123'
        if not user.check_password('password123'):
            print(f"User '{user.username}' has invalid password, fixing...")
            user.set_password('password123')
            fixed_count += 1
    
    if fixed_count > 0:
        db.session.commit()
        print(f"\nFixed {fixed_count} users with password 'password123'")
    else:
        print("All users have valid passwords")
    
    # Verify
    print("\nVerifying all users can login with 'password123':")
    all_valid = True
    for user in User.query.all():
        can_login = user.check_password('password123')
        print(f"  - {user.username}: {can_login}")
        if not can_login:
            all_valid = False
    
    if all_valid:
        print("\n✓ All users can now login with 'password123'")
    else:
        print("\n✗ Some users still have issues")
