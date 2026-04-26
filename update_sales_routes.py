import os

path = 'app/routes/sales.py'
with open(path, 'r') as f:
    content = f.read()

# Add salesman_id to request.args
old_line = "to_date = request.args.get('to_date')"
new_line = "to_date = request.args.get('to_date')\n    salesman_id = request.args.get('salesman_id', type=int)"
if old_line in content:
    content = content.replace(old_line, new_line)

# Add salesman filter to query
old_query = "query = query.filter(Sale.status == status)"
new_query = "query = query.filter(Sale.status == status)\n    \n    if salesman_id:\n        query = query.filter(Sale.salesman_id == salesman_id)"
if old_query in content:
    content = content.replace(old_query, new_query)

# Load salesmen and update template context
old_render = "return render_template('sales/invoices.html', \n                         sales=sales, \n                         current_status=status,\n                         from_date=from_date,\n                         to_date=to_date,"
new_render = "    # Load salesmen for filter dropdown\n    salesmen = Salesman.query.filter_by(is_active=True).all()\n    \n    return render_template('sales/invoices.html', \n                         sales=sales, \n                         current_status=status,\n                         from_date=from_date,\n                         to_date=to_date,\n                         salesman_id=salesman_id,\n                         salesmen=salesmen,"

if old_render in content:
    content = content.replace(old_render, new_render)

with open(path, 'w') as f:
    f.write(content)

print("Successfully updated app/routes/sales.py")
