import os

path = 'app/templates/base.html'
with open(path, 'r') as f:
    content = f.read()

# 1. Desktop Sidebar (usually further down)
old_desktop = """<a class="nav-link" href="{{ url_for('sales.customers') }}">
                            <i class="fas fa-user-friends me-2"></i> Customers
                        </a>"""

new_desktop = """<a class="nav-link" href="{{ url_for('sales.customers') }}">
                            <i class="fas fa-user-friends me-2"></i> Customers
                        </a>
                        <a class="nav-link" href="{{ url_for('sales.customer_groups_list') }}">
                            <i class="fas fa-layer-group me-2"></i> Customer Groups
                        </a>"""

if old_desktop in content:
    content = content.replace(old_desktop, new_desktop)

# 2. Mobile Sidebar
old_mobile = """<a class="nav-link" href="{{ url_for('sales.customers') }}">
                    <i class="fas fa-user-friends me-2"></i> Customers
                </a>"""

new_mobile = """<a class="nav-link" href="{{ url_for('sales.customers') }}">
                    <i class="fas fa-user-friends me-2"></i> Customers
                </a>
                <a class="nav-link" href="{{ url_for('sales.customer_groups_list') }}">
                    <i class="fas fa-layer-group me-2"></i> Customer Groups
                </a>"""

if old_mobile in content:
    content = content.replace(old_mobile, new_mobile)

with open(path, 'w') as f:
    f.write(content)

print("Successfully updated base.html sidebar (mobile and desktop)")
