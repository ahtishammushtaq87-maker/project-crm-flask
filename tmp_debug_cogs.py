from run import app
from app.routes.reports import cogs_report
from app.models import User
from flask_login import login_user

with app.test_request_context('/reports/cogs-report', method='GET'):
    user = User.query.filter_by(username='admin').first()
    login_user(user)
    out = cogs_report()
    print(type(out))
    print(str(out)[:1200])
