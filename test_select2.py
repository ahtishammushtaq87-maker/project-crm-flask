from wtforms import Form, SelectField
from werkzeug.datastructures import MultiDict

class F(Form):
    s = SelectField('s', choices=[(True, 'Active'), (False, 'Inactive')], coerce=lambda x: x == 'True')

f = F(MultiDict({'s': 'True'}))
print('data', f.s.data, 'choices', [c[0] for c in f.s.choices], 'validate', f.validate(), 'errors', f.s.errors)

class G(Form):
    s = SelectField('s', choices=[('True', 'Active'), ('False', 'Inactive')], coerce=lambda x: x == 'True')

g = G(MultiDict({'s': 'True'}))
print('data2', g.s.data, 'choices2', [c[0] for c in g.s.choices], 'validate2', g.validate(), 'errors2', g.s.errors)
