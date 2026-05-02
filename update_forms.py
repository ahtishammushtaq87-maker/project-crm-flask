import re

with open('app/forms.py', 'r', encoding='utf-8') as f:
    content = f.read()

modules = [
    'sales', 'purchases', 'inventory', 'expenses', 'returns',
    'vendors', 'customers', 'reports', 'settings', 'manufacturing',
    'production', 'warehouse', 'attendance', 'salary', 'targets',
    'dashboard', 'accounting', 'salesmen', 'product_dev', 'categories',
    'customer_groups', 'tasks', 'profit_loss', 'users'
]

add_fields = []
for m in modules:
    label = m.title().replace('_', ' ')
    add_fields.append(f"    can_add_{m} = BooleanField('Add {label}', default=False)")
for m in modules:
    label = m.title().replace('_', ' ')
    add_fields.append(f"    can_edit_{m} = BooleanField('Edit {label}', default=False)")
for m in modules:
    label = m.title().replace('_', ' ')
    add_fields.append(f"    can_delete_{m} = BooleanField('Delete {label}', default=False)")

fields_str = '\n'.join(add_fields) + '\n'

new_content = re.sub(
    r"(    can_view_users = BooleanField\('.*?', default=False\))",
    r"\1\n" + fields_str,
    content
)

with open('app/forms.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
