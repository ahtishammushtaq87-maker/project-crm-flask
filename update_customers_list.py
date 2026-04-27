import os

path = 'app/templates/sales/customers.html'
with open(path, 'r') as f:
    content = f.read()

# 1. Update Table Headers
old_headers = '<th>Name</th>'
new_headers = '<th>Name</th>\n                            <th>Company</th>\n                            <th>Group</th>'

if old_headers in content:
    content = content.replace(old_headers, new_headers)

# 2. Update Table Rows
old_row = '<td>{{ customer.name }}</td>'
new_row = """<td>{{ customer.name }}</td>
                            <td>{{ customer.company_name or '-' }}</td>
                            <td>
                                {% if customer.group %}
                                <span class="badge bg-secondary text-white" style="font-size: 0.8rem;">{{ customer.group.name }}</span>
                                {% else %}
                                -
                                {% endif %}
                            </td>"""

if old_row in content:
    content = content.replace(old_row, new_row)

with open(path, 'w') as f:
    f.write(content)

print("Successfully updated customers list template")
