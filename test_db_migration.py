from app import create_app, db
from app.models import User
import sys

try:
    app = create_app()
    with app.app_context():
        u = User.query.first()
        if u and hasattr(u, 'can_add_sales'):
            print('Migration successful: can_add_sales exists!')
            print(f'Admin user can_add_sales: {getattr(u, "can_add_sales")}')
        elif not u:
            print('No users in DB, but initialized ok.')
        else:
            print('Failed: attribute missing on User model!')
            sys.exit(1)
except Exception as e:
    print(f'Error during init: {e}')
    sys.exit(1)
