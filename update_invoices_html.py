import os

path = 'app/templates/sales/invoices.html'
with open(path, 'r') as f:
    content = f.read()

# 1. Add salesman filter to form
old_form_part = '<div class="col-md-3">\n                    <label for="to_date" class="form-label">To Date</label>'
new_form_part = """<div class="col-md-3">
                    <label for="to_date" class="form-label">To Date</label>""" 
# I'll try a different approach, replace the Filter button div.

old_button_div = '<div class="col-md-2">\n                    <button type="submit" class="btn btn-primary d-block">Filter</button>\n                </div>'
new_button_div = """<div class="col-md-2">
                    <label for="salesman_id" class="form-label">Salesman</label>
                    <select name="salesman_id" id="salesman_id" class="form-select">
                        <option value="">All</option>
                        {% for s in salesmen %}
                        <option value="{{ s.id }}" {% if salesman_id == s.id %}selected{% endif %}>{{ s.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-1">
                    <label class="form-label d-none d-md-block">&nbsp;</label>
                    <button type="submit" class="btn btn-primary d-block w-100">Filter</button>
                </div>"""

if old_button_div in content:
    content = content.replace(old_button_div, new_button_div)

# 2. Update status links to preserve salesman_id
content = content.replace("from_date=from_date, to_date=to_date)", "from_date=from_date, to_date=to_date, salesman_id=salesman_id)")

# 3. Add Salesman column to table
old_table_header = '<th>Customer</th>\n                            <th>Vendor</th>'
new_table_header = '<th>Customer</th>\n                            <th>Salesman</th>\n                            <th>Vendor</th>'

if old_table_header in content:
    content = content.replace(old_table_header, new_table_header)

old_table_row = '<td>{{ sale.customer.name if sale.customer else "Walk-in" }}</td>\n                            <td>{{ sale.vendor.name if sale.vendor else "-" }}</td>'
new_table_row = '<td>{{ sale.customer.name if sale.customer else "Walk-in" }}</td>\n                            <td>{{ sale.salesman.name if sale.salesman else "-" }}</td>\n                            <td>{{ sale.vendor.name if sale.vendor else "-" }}</td>'

if old_table_row in content:
    content = content.replace(old_table_row, new_table_row)

with open(path, 'w') as f:
    f.write(content)

print("Successfully updated invoices.html")
