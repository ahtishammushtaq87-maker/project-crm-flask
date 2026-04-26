import os

path = 'app/routes/sales.py'
with open(path, 'r') as f:
    content = f.read()

new_routes = """
# --- Salesman Management ---

@bp.route('/salesmen')
@login_required
def salesmen_list():
    salesmen = Salesman.query.all()
    return render_template('sales/salesmen.html', salesmen=salesmen)

@bp.route('/salesman/add', methods=['GET', 'POST'])
@login_required
def add_salesman():
    form = SalesmanForm()
    if form.validate_on_submit():
        salesman = Salesman(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            commission_rate=form.commission_rate.data,
            is_active=form.is_active.data
        )
        db.session.add(salesman)
        db.session.commit()
        flash('Salesman added successfully!', 'success')
        return redirect(url_for('sales.salesmen_list'))
    return render_template('sales/salesman_form.html', form=form, title='Add Salesman')

@bp.route('/salesman/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_salesman(id):
    salesman = Salesman.query.get_or_404(id)
    form = SalesmanForm(obj=salesman)
    if form.validate_on_submit():
        salesman.name = form.name.data
        salesman.email = form.email.data
        salesman.phone = form.phone.data
        salesman.address = form.address.data
        salesman.commission_rate = form.commission_rate.data
        salesman.is_active = form.is_active.data
        db.session.commit()
        flash('Salesman updated successfully!', 'success')
        return redirect(url_for('sales.salesmen_list'))
    return render_template('sales/salesman_form.html', form=form, title='Edit Salesman', salesman=salesman)

@bp.route('/salesman/delete/<int:id>', methods=['POST'])
@login_required
def delete_salesman(id):
    salesman = Salesman.query.get_or_404(id)
    if salesman.sales:
        flash('Cannot delete salesman with associated sales records.', 'danger')
        return redirect(url_for('sales.salesmen_list'))
    db.session.delete(salesman)
    db.session.commit()
    flash('Salesman deleted successfully.', 'info')
    return redirect(url_for('sales.salesmen_list'))

@bp.route('/salesman/quick-add', methods=['POST'])
@login_required
def quick_add_salesman():
    name = request.form.get('name')
    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400
    
    salesman = Salesman(name=name)
    db.session.add(salesman)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'salesman': {
            'id': salesman.id,
            'name': salesman.name
        }
    })
"""

# Append if not already present
if '@bp.route(\'/salesmen\')' not in content:
    content += new_routes

with open(path, 'w') as f:
    f.write(content)

print("Successfully added Salesman routes to app/routes/sales.py")
