import os
import re

ui_modules_map = {
    'accounting': 'accounting',
    'inventory': 'inventory',
    'purchase': 'purchases',
    'sales': 'sales',
    'manufacturing': 'manufacturing',
    'production': 'production',
    'salary': 'salary',
    'warehouse': 'warehouse',
    'categories': 'categories',
    'users': 'users',
    'targets': 'targets',
    'returns': 'returns',
    'product_development': 'product_dev',
    'attendance': 'attendance',
    'dashboard': 'dashboard',
    'reports': 'reports'
}

def patch_template(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    offset = 0
    modifications = []

    # Find all url_for
    for match in re.finditer(r"url_for\('([^']+)'", content):
        url_target = match.group(1)
        if '.' not in url_target:
            continue
            
        module_name, route_name = url_target.split('.', 1)
        if module_name not in ui_modules_map:
            continue
            
        perm_module = ui_modules_map[module_name]
        
        # Determine action
        action = None
        if re.search(r'^(create|add)', route_name):
            action = 'add'
        elif re.search(r'^(edit|update)', route_name):
            action = 'edit'
        elif re.search(r'^(delete|bulk_delete)', route_name):
            action = 'delete'
            
        if not action:
            continue
            
        # We found a restricted action url. We need to find its container tag.
        match_start = match.start()
        
        # Look backwards for '<a ', '<form ', '<button '
        # We only look back up to 500 characters to prevent false positives
        search_window_start = max(0, match_start - 500)
        window = content[search_window_start:match_start]
        
        tag_starts = [(window.rfind('<a '), 'a'), (window.rfind('<form '), 'form'), (window.rfind('<button '), 'button')]
        # get the closest tag start
        valid_starts = [(idx, tag) for idx, tag in tag_starts if idx != -1]
        if not valid_starts:
            continue
        
        closest_start_rel_idx, tag_name = max(valid_starts, key=lambda x: x[0])
        tag_start_absolute = search_window_start + closest_start_rel_idx
        
        # Look forward for the closing tag: '</a>', '</form>', '</button>'
        closing_tag = f'</{tag_name}>'
        closing_tag_idx = content.find(closing_tag, match_start)
        
        if closing_tag_idx == -1:
            continue
            
        tag_end_absolute = closing_tag_idx + len(closing_tag)
        
        # Make sure we didn't already wrap this
        before_tag = content[max(0, tag_start_absolute-50):tag_start_absolute]
        if '{% if current_user.has_permission' in before_tag:
            continue
            
        modifications.append({
            'start': tag_start_absolute,
            'end': tag_end_absolute,
            'perm_module': perm_module,
            'action': action,
            'tag_name': tag_name
        })

    # To avoid overlapping modifications messing up absolute indices,
    # we filter out nested modifications (e.g. button inside form)
    # Actually, form wraps button. We only wrap the outermost if both exist.
    filtered_mods = []
    # Sort by start asc
    modifications.sort(key=lambda x: x['start'])
    for m in modifications:
        is_nested = False
        for fm in filtered_mods:
            if fm['start'] <= m['start'] and fm['end'] >= m['end']:
                is_nested = True
                break
        if not is_nested:
            filtered_mods.append(m)

    # Sort descending so indices don't shift during insertion
    filtered_mods.sort(key=lambda x: x['start'], reverse=True)
    
    new_content = content
    for m in filtered_mods:
        start = m['start']
        end = m['end']
        perm_module = m['perm_module']
        action = m['action']
        
        insertion_start = f"{{% if current_user.has_permission('{perm_module}', '{action}') %}}\n"
        insertion_end = "\n{% endif %}"
        
        # preserve leading whitespace before start for proper indentation
        line_start = new_content.rfind('\n', 0, start)
        if line_start != -1:
            leading_space = new_content[line_start+1:start]
            if leading_space.isspace():
                insertion_start = leading_space + insertion_start
                insertion_end = insertion_end + leading_space
        
        new_content = new_content[:start] + insertion_start + new_content[start:end] + insertion_end + new_content[end:]

    if new_content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

templates_dir = 'app/templates'
patched_files = 0
for root, dirs, files in os.walk(templates_dir):
    # omit components and auth
    if 'components' in root or 'auth' in root:
        continue
    for file in files:
        if file.endswith('.html'):
            if patch_template(os.path.join(root, file)):
                patched_files += 1

print(f"Patched {patched_files} UI templates successfully!")
