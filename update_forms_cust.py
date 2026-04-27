import os

path = 'app/forms.py'
with open(path, 'r') as f:
    content = f.read()

# 1. Add CustomerGroupForm
group_form = """
class CustomerGroupForm(FlaskForm):
    name = StringField('Group Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    submit = SubmitField('Save Group')
"""

if 'class CustomerGroupForm' not in content:
    content += group_form

# 2. Update CustomerForm
if 'company_name =' not in content:
    content = content.replace("name = StringField('Customer Name', validators=[DataRequired()])", 
                               "name = StringField('Customer Name', validators=[DataRequired()])\n    company_name = StringField('Company Name')\n    group_id = SelectField('Customer Group', coerce=int, validators=[Optional()])")

with open(path, 'w') as f:
    f.write(content)

print("Successfully updated app/forms.py")
