import os
import re

routes_dir = 'app/routes'
modules_map = {
    'accounting.py': 'accounting',
    'attendance.py': 'attendance',
    'categories.py': 'categories',
    'dashboard.py': 'dashboard',
    'inventory.py': 'inventory',
    'manufacturing.py': 'manufacturing',
    'product_development.py': 'product_dev',
    'production.py': 'production',
    'purchase.py': 'purchases',
    'reports.py': 'reports',
    'reports_attendance.py': 'reports',
    'returns.py': 'returns',
    'salary.py': 'salary',
    'sales.py': 'sales',
    'targets.py': 'targets',
    'users.py': 'users',
    'warehouse.py': 'warehouse'
}

for filename in os.listdir(routes_dir):
    if not filename.endswith('.py') or filename in ['__init__.py', 'auth.py', 'filters.py']:
        continue
        
    filepath = os.path.join(routes_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if 'from app.utils import permission_required' not in content:
        # insert at top
        content = re.sub(
            r"(from flask import .*?\n)",
            r"\1from app.utils import permission_required\n",
            content,
            count=1
        )
        if 'permission_required' not in content:
            content = "from app.utils import permission_required\n" + content
            
    module_name = modules_map.get(filename, 'settings')
    
    # We will search for @login_required followed by def func_name
    # and if it looks like an action route, insert @permission_required
    
    def replacer(match):
        route_decorator = match.group(1)
        login_decorator = match.group(2)
        func_def = match.group(3)
        
        # If it already has permission_required, skip
        if '@permission_required' in route_decorator or '@permission_required' in login_decorator or '@permission_required' in func_def:
            return match.group(0)
            
        action = 'view'
        # Heuristics based on URL
        if re.search(r"/(create|add)", route_decorator):
            action = 'add'
        elif re.search(r"/(edit|update)", route_decorator):
            action = 'edit'
        elif re.search(r"/delete", route_decorator, re.IGNORECASE):
            action = 'delete'
        
        if action != 'view':
            # Insert decorator
            return f"{route_decorator}{login_decorator}@permission_required('{module_name}', action='{action}')\n{func_def}"
        return match.group(0)

    # Pattern: @bp.route(...) ... @login_required\n def ...
    # Be careful with spacing
    pattern = r"(@bp\.route[^\n]+\n(?:@[^\n]+\n)*?)(@login_required\n)(def [^\n]+\n)"
    new_content = re.sub(pattern, replacer, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

print("Backend patched successfully.")
