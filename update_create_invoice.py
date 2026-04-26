import os

path = 'app/routes/sales.py'
with open(path, 'r') as f:
    content = f.read()

# 1. Update create_invoice choices
old_choices = "form.customer_id.choices = [(0, 'Walk-in Customer')] + [(c.id, c.name) for c in customers]"
new_choices = """form.customer_id.choices = [(0, 'Walk-in Customer')] + [(c.id, c.name) for c in customers]
    form.salesman_id.choices = [(0, 'No Salesman')] + [(s.id, s.name) for s in Salesman.query.filter_by(is_active=True).all()]"""

if old_choices in content:
    content = content.replace(old_choices, new_choices)

# 2. Add salesman list to the return context
old_render_create = "return render_template('sales/create_invoice.html', form=form, products=products, customers=customers, vendors=vendors, currencies=currencies, now=datetime.now(), customer_advances=customer_advances, customer_total_advances=customer_total_advances)"
new_render_create = "    salesmen = Salesman.query.filter_by(is_active=True).all()\n    return render_template('sales/create_invoice.html', form=form, products=products, customers=customers, vendors=vendors, currencies=currencies, now=datetime.now(), customer_advances=customer_advances, customer_total_advances=customer_total_advances, salesmen=salesmen)"

if old_render_create in content:
    content = content.replace(old_render_create, new_render_create)

# 3. Capture salesman_id in POST
old_post_vars = "selected_vendor_id = request.form.get('vendor_id')"
new_post_vars = "selected_vendor_id = request.form.get('vendor_id')\n        salesman_id = request.form.get('salesman_id')"

if old_post_vars in content:
    content = content.replace(old_post_vars, new_post_vars)

# 4. Add salesman_id to Sale creation
old_sale_init = "exchange_rate=float(request.form.get('exchange_rate', 1)),"
new_sale_init = "exchange_rate=float(request.form.get('exchange_rate', 1)),\n            salesman_id=salesman_id if salesman_id and salesman_id != '0' else None,"

if old_sale_init in content:
    content = content.replace(old_sale_init, new_sale_init)

with open(path, 'w') as f:
    f.write(content)

print("Successfully updated create_invoice in app/routes/sales.py")
