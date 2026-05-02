import re

with open('app/routes/users.py', 'r', encoding='utf-8') as f:
    content = f.read()

modules = [
    'sales', 'purchases', 'inventory', 'expenses', 'returns',
    'vendors', 'customers', 'reports', 'settings', 'manufacturing',
    'production', 'warehouse', 'attendance', 'salary', 'targets',
    'dashboard', 'accounting', 'salesmen', 'product_dev', 'categories',
    'customer_groups', 'tasks', 'profit_loss', 'users'
]

# 1. Update create_user assignment block
create_fields = []
for action in ['add', 'edit', 'delete']:
    for m in modules:
        create_fields.append(f"            can_{action}_{m}=form.can_{action}_{m}.data,")
# Remove trailing comma on last one is tricky, actually we can just pass them with trailing commas, python allows it
create_str = '\n'.join(create_fields)

content = re.sub(
    r"(can_view_users=form.can_view_users.data)",
    r"\1,\n" + create_str,
    content
)

# 2. Update edit_user POST block
edit_post_fields = []
for action in ['add', 'edit', 'delete']:
    for m in modules:
        edit_post_fields.append(f"        user.can_{action}_{m} = form.can_{action}_{m}.data")
edit_post_str = '\n'.join(edit_post_fields)

content = re.sub(
    r"(user.can_view_users = form.can_view_users.data)",
    r"\1\n" + edit_post_str,
    content
)

# 3. Update edit_user GET block
edit_get_fields = []
for action in ['add', 'edit', 'delete']:
    for m in modules:
        edit_get_fields.append(f"        form.can_{action}_{m}.data = getattr(user, 'can_{action}_{m}', False)")
edit_get_str = '\n'.join(edit_get_fields)

content = re.sub(
    r"(form.can_view_users.data = getattr\(user, 'can_view_users', False\))",
    r"\1\n" + edit_get_str,
    content
)

with open('app/routes/users.py', 'w', encoding='utf-8') as f:
    f.write(content)
