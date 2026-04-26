import os

path = 'app/templates/base.html'
with open(path, 'r') as f:
    content = f.read()

# 1. Update Mobile Sidebar
old_mobile_sales = """                <a class="nav-link" href="{{ url_for('sales.invoices') }}">
                    <i class="fas fa-shopping-cart me-2"></i> Sales
                </a>
                <a class="nav-link" href="{{ url_for('returns.return_list') }}">
                    <i class="fas fa-undo me-2"></i> Sales Returns
                </a>"""

new_mobile_sales = """                <a class="nav-link" href="{{ url_for('sales.invoices') }}">
                    <i class="fas fa-shopping-cart me-2"></i> Sales
                </a>
                <a class="nav-link" href="{{ url_for('returns.return_list') }}">
                    <i class="fas fa-undo me-2"></i> Sales Returns
                </a>
                <a class="nav-link" href="{{ url_for('sales.salesmen_list') }}">
                    <i class="fas fa-user-tag me-2"></i> Salesmen
                </a>"""

if old_mobile_sales in content:
    content = content.replace(old_mobile_sales, new_mobile_sales)

# 2. Update Desktop Sidebar
old_desktop_sales = """                        <a class="nav-link" href="{{ url_for('sales.invoices') }}">
                            <i class="fas fa-shopping-cart me-2"></i> Sales
                        </a>
                        <a class="nav-link" href="{{ url_for('returns.return_list') }}">
                            <i class="fas fa-undo me-2"></i> Sales Returns
                        </a>"""

new_desktop_sales = """                        <a class="nav-link" href="{{ url_for('sales.invoices') }}">
                            <i class="fas fa-shopping-cart me-2"></i> Sales
                        </a>
                        <a class="nav-link" href="{{ url_for('returns.return_list') }}">
                            <i class="fas fa-undo me-2"></i> Sales Returns
                        </a>
                        <a class="nav-link" href="{{ url_for('sales.salesmen_list') }}">
                            <i class="fas fa-user-tag me-2"></i> Salesmen
                        </a>"""

if old_desktop_sales in content:
    content = content.replace(old_desktop_sales, new_desktop_sales)

with open(path, 'w') as f:
    f.write(content)

print("Successfully updated base.html")
