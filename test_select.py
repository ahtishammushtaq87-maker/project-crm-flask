from app import create_app
from app.forms import UserEditForm
from werkzeug.datastructures import MultiDict

app = create_app()
with app.test_request_context():
    f = UserEditForm()
    print('choices', f.is_active.choices)
    f.is_active.data = True
    print('assign bool', f.is_active.data)
    print('validate1', f.validate())

    f2 = UserEditForm(formdata=MultiDict({'is_active':'True'}))
    print('post raw', f2.is_active.raw_data, 'data', f2.is_active.data, 'validate2', f2.validate(), 'errors', f2.is_active.errors)
