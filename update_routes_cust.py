import os

path = 'app/routes/sales.py'
with open(path, 'r') as f:
    content = f.read()

# 1. Update add_customer
# Need to populate group choices and save the new fields
old_add_customer = """def add_customer():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            gst_number=form.gst_number.data,
            payment_method=form.payment_method.data
        )"""

new_add_customer = """def add_customer():
    form = CustomerForm()
    groups = CustomerGroup.query.filter_by(is_active=True).all()
    form.group_id.choices = [(0, '— Select Group —')] + [(g.id, g.name) for g in groups]
    
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            company_name=form.company_name.data,
            group_id=form.group_id.data if form.group_id.data != 0 else None,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            gst_number=form.gst_number.data,
            payment_method=form.payment_method.data
        )"""

if old_add_customer in content:
    content = content.replace(old_add_customer, new_add_customer)

# 2. Update edit_customer
old_edit_customer = """def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    form = CustomerForm(obj=customer)
    
    if form.validate_on_submit():
        customer.name = form.name.data
        customer.email = form.email.data
        customer.phone = form.phone.data
        customer.address = form.address.data
        customer.gst_number = form.gst_number.data
        customer.payment_method = form.payment_method.data"""

new_edit_customer = """def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    form = CustomerForm(obj=customer)
    groups = CustomerGroup.query.filter_by(is_active=True).all()
    form.group_id.choices = [(0, '— Select Group —')] + [(g.id, g.name) for g in groups]
    
    if form.validate_on_submit():
        customer.name = form.name.data
        customer.company_name = form.company_name.data
        customer.group_id = form.group_id.data if form.group_id.data != 0 else None
        customer.email = form.email.data
        customer.phone = form.phone.data
        customer.address = form.address.data
        customer.gst_number = form.gst_number.data
        customer.payment_method = form.payment_method.data"""

if old_edit_customer in content:
    content = content.replace(old_edit_customer, new_edit_customer)

# 3. Add CustomerGroup CRUD routes at the end
group_routes = """
# --- Customer Group Management ---

@bp.route('/customer-groups')
@login_required
def customer_groups_list():
    groups = CustomerGroup.query.all()
    return render_template('sales/customer_groups.html', groups=groups)

@bp.route('/customer-group/add', methods=['GET', 'POST'])
@login_required
def add_customer_group():
    form = CustomerGroupForm()
    if form.validate_on_submit():
        group = CustomerGroup(
            name=form.name.data,
            description=form.description.data
        )
        db.session.add(group)
        db.session.commit()
        flash('Customer Group added successfully!', 'success')
        return redirect(url_for('sales.customer_groups_list'))
    return render_template('sales/customer_group_form.html', form=form, title='Add Customer Group')

@bp.route('/customer-group/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_customer_group(id):
    group = CustomerGroup.query.get_or_404(id)
    form = CustomerGroupForm(obj=group)
    if form.validate_on_submit():
        group.name = form.name.data
        group.description = form.description.data
        db.session.commit()
        flash('Customer Group updated successfully!', 'success')
        return redirect(url_for('sales.customer_groups_list'))
    return render_template('sales/customer_group_form.html', form=form, title='Edit Customer Group', group=group)

@bp.route('/customer-group/delete/<int:id>', methods=['POST'])
@login_required
def delete_customer_group(id):
    group = CustomerGroup.query.get_or_404(id)
    if group.customers:
        flash('Cannot delete group with associated customers.', 'danger')
        return redirect(url_for('sales.customer_groups_list'))
    db.session.delete(group)
    db.session.commit()
    flash('Customer Group deleted successfully.', 'info')
    return redirect(url_for('sales.customer_groups_list'))

@bp.route('/customer-group/quick-add', methods=['POST'])
@login_required
def quick_add_customer_group():
    name = request.form.get('name')
    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400
    
    if CustomerGroup.query.filter_by(name=name).first():
        return jsonify({'success': False, 'message': 'Group already exists'}), 400

    group = CustomerGroup(name=name)
    db.session.add(group)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'group': {
            'id': group.id,
            'name': group.name
        }
    })
"""

if 'customer-group/quick-add' not in content:
    content += group_routes

with open(path, 'w') as f:
    f.write(content)

print("Successfully updated app/routes/sales.py")
