from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.utils import permission_required
from flask_login import login_required, current_user
from app import db
from app.utils import log_activity
from datetime import datetime
from sqlalchemy import inspect, func, or_
import random
import string

bp = Blueprint('product_development', __name__, url_prefix='/product-development')


def generate_pdv_code():
    """Generate unique PDV code"""
    year = datetime.now().year
    prefix = f"PDV-{year}-"
    last_project = PDProject.query.filter(
        PDProject.pdv_code.like(f"{prefix}%")
    ).order_by(PDProject.pdv_code.desc()).first()
    
    if last_project:
        try:
            last_num = int(last_project.pdv_code.split('-')[-1])
            new_num = last_num + 1
        except:
            new_num = 1
    else:
        new_num = 1
    
    return f"{prefix}{new_num:04d}"


def generate_asset_tag():
    """Generate unique asset tag for PD assets"""
    prefix = "AST-PD-"
    last_asset = PDAsset.query.order_by(PDAsset.id.desc()).first()
    new_id = (last_asset.id + 1) if last_asset else 1
    return f"{prefix}{new_id:05d}"


DEVELOPMENT_EXPENSE_CATEGORIES = {
    'Sample Purchase', 'Reverse Engineering', 'Measurement', 'CAD', 'Prototype', 'Testing'
}

TOOLING_EXPENSE_CATEGORIES = {
    'Mold', 'Die', 'Fixture', 'Pattern', 'Jig', 'Gauge'
}

PRODUCTION_DIRECT_CATEGORIES = {
    'Raw Material', 'Purchased Components', 'Machining', 'Casting'
}

FACTORY_OVERHEAD_CATEGORIES = {
    'Electricity', 'Maintenance', 'Factory Wages'
}

ADMIN_EXPENSE_CATEGORIES = {
    'Office Rent', 'Salaries', 'Marketing', 'Travel'
}

LOSS_EXPENSE_CATEGORIES = {
    'Scrap', 'Prototype Failure', 'Warranty'
}


def validate_pd_expense(project_id, tooling_id, category, item_code, work_order_id, cost_center, amortization_selected, expected_recovery_quantity):
    if category in DEVELOPMENT_EXPENSE_CATEGORIES and not project_id:
        return 'Development expense must be linked to a PD project.'
    if category in TOOLING_EXPENSE_CATEGORIES and (not project_id or not tooling_id):
        return 'Tooling expense must be linked to a PD project and tooling record.'
    if category in PRODUCTION_DIRECT_CATEGORIES and not (item_code or work_order_id):
        return 'Production direct cost must include an item code or work order.'
    if category in FACTORY_OVERHEAD_CATEGORIES and (not cost_center or cost_center.strip().lower() != 'factory'):
        return 'Factory overhead costs must use cost center "Factory".'
    if category in ADMIN_EXPENSE_CATEGORIES:
        # Admin expenses are tracked separately and should not be included in manufacturing cost
        pass
    if amortization_selected and (expected_recovery_quantity is None or expected_recovery_quantity <= 0):
        return 'Expected recovery quantity is required when amortization is selected.'
    return None


def project_has_invalid_expenses(project):
    for expense in project.development_expenses:
        error = validate_pd_expense(
            expense.project_id,
            expense.tooling_id,
            expense.expense_category,
            expense.item_code,
            expense.work_order_id,
            expense.cost_center,
            expense.amortization_selected,
            expense.expected_recovery_quantity
        )
        if error:
            return error
    return None


@bp.route('/')
@login_required
def index():
    """Dashboard with all projects"""
    projects = PDProject.query.order_by(PDProject.created_at.desc()).all()
    today = datetime.now().date()
    
    total_projects = len(projects)
    active_projects = len([p for p in projects if p.status == 'Active'])
    completed_projects = len([p for p in projects if p.status == 'Completed'])
    delayed_projects = len([p for p in projects if p.is_delayed])
    total_investment = sum(p.total_investment for p in projects)
    
    near_deadline = [p for p in projects if p.promise_date and p.status not in ['Completed'] 
                     and (p.promise_date - today).days <= 7]
    
    return render_template('product_development/index.html',
                         projects=projects,
                         total_projects=total_projects,
                         active_projects=active_projects,
                         completed_projects=completed_projects,
                         delayed_projects=delayed_projects,
                         total_investment=total_investment,
                         near_deadline=near_deadline,
                         today=today)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('product_dev', action='add')
def create():
    """Create new product development project"""
    finished_goods = Product.query.filter(Product.is_manufactured == True, Product.is_active == True).all()
    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    users = User.query.filter_by(is_active=True).all()
    today = datetime.now().date().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        project = PDProject(
            pdv_code=generate_pdv_code(),
            product_name=request.form.get('product_name'),
            sku_id=request.form.get('sku_id') or None,
            product_category_id=request.form.get('product_category_id') or None,
            cost=float(request.form.get('cost') or 0),
            damage_percent=float(request.form.get('damage_percent') or 0),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else None,
            promise_date=datetime.strptime(request.form.get('promise_date'), '%Y-%m-%d').date() if request.form.get('promise_date') else None,
            budget=float(request.form.get('budget') or 0),
            approved_budget=float(request.form.get('approved_budget') or 0),
            oem_part_number=request.form.get('oem_part_number'),
            aftermarket_part_number=request.form.get('aftermarket_part_number'),
            vehicle_application=request.form.get('vehicle_application'),
            requested_by=request.form.get('requested_by') or None,
            project_owner_id=request.form.get('project_owner_id') or None,
            target_market=request.form.get('target_market'),
            expected_monthly_demand=float(request.form.get('expected_monthly_demand') or 0),
            target_selling_price=float(request.form.get('target_selling_price') or 0),
            status='Draft',
            current_phase=1,
            description=request.form.get('description'),
            created_by=current_user.id
        )
        db.session.add(project)
        db.session.commit()
        
        # Create initial approval record
        approval = PDApproval(project_id=project.id)
        db.session.add(approval)
        db.session.commit()
        
        flash(f'Project {project.pdv_code} created successfully!', 'success')
        return redirect(url_for('product_development.view', project_id=project.id))
    
    return render_template('product_development/create.html', finished_goods=finished_goods, categories=categories, users=users, today=today)


@bp.route('/view/<int:project_id>')
@login_required
def view(project_id):
    """View project details with all phases"""
    project = PDProject.query.get_or_404(project_id)
    
    # All products for Phase 1 modals (BOM/Components)
    all_products = Product.query.filter_by(is_active=True).all()
    # Only finished goods for project linking (create/edit)
    finished_goods = Product.query.filter(Product.is_manufactured == True, Product.is_active == True).all()
    vendors = Vendor.query.filter_by(is_active=True).all()
    users = User.query.filter_by(is_active=True).all()
    today = datetime.now().date().strftime('%Y-%m-%d')
    
    return render_template('product_development/view.html', project=project, products=all_products, finished_goods=finished_goods, vendors=vendors, users=users, today=today)


@bp.route('/edit/<int:project_id>', methods=['GET', 'POST'])
@login_required
@permission_required('product_dev', action='edit')
def edit(project_id):
    """Edit project details"""
    project = PDProject.query.get_or_404(project_id)
    finished_goods = Product.query.filter(Product.is_manufactured == True, Product.is_active == True).all()
    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    users = User.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        project.product_name = request.form.get('product_name')
        project.sku_id = request.form.get('sku_id') or None
        project.product_category_id = request.form.get('product_category_id') or None
        project.cost = float(request.form.get('cost') or 0)
        project.damage_percent = float(request.form.get('damage_percent') or 0)
        project.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else None
        project.promise_date = datetime.strptime(request.form.get('promise_date'), '%Y-%m-%d').date() if request.form.get('promise_date') else None
        project.budget = float(request.form.get('budget') or 0)
        project.approved_budget = float(request.form.get('approved_budget') or 0)
        project.oem_part_number = request.form.get('oem_part_number')
        project.aftermarket_part_number = request.form.get('aftermarket_part_number')
        project.vehicle_application = request.form.get('vehicle_application')
        project.requested_by = request.form.get('requested_by') or None
        project.project_owner_id = request.form.get('project_owner_id') or None
        project.target_market = request.form.get('target_market')
        project.expected_monthly_demand = float(request.form.get('expected_monthly_demand') or 0)
        project.target_selling_price = float(request.form.get('target_selling_price') or 0)
        project.status = request.form.get('status')
        project.description = request.form.get('description')
        
        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('product_development.view', project_id=project.id))
    
    return render_template('product_development/edit.html', project=project, finished_goods=finished_goods, categories=categories, users=users)


@bp.route('/delete/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='delete')
def delete(project_id):
    """Delete project"""
    project = PDProject.query.get_or_404(project_id)
    pdv_code = project.pdv_code
    
    db.session.delete(project)
    db.session.commit()
    
    flash(f'Project {pdv_code} deleted!', 'success')
    return redirect(url_for('product_development.index'))


@bp.route('/phase/<int:project_id>/<int:phase>')
@login_required
def phase(project_id, phase):
    """View specific phase - redirect to main view with anchor"""
    return redirect(url_for('product_development.view', project_id=project_id, _anchor=f'phase{phase}'))


# ==================== PHASE 1: MATERIALS & COMPONENTS (BOM + COMPONENTS) ====================

@bp.route('/bom/add/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_bom(project_id):
    """Add BOM item"""
    project = PDProject.query.get_or_404(project_id)
    
    bom_item = PDProjectBOM(
        project_id=project_id,
        material_name=request.form.get('material_name'),
        sku_id=request.form.get('sku_id') or None,
        quantity_per_unit=float(request.form.get('quantity_per_unit') or 1),
        estimated_cost=float(request.form.get('estimated_cost') or 0),
        notes=request.form.get('notes')
    )
    db.session.add(bom_item)
    
    # Keep in Phase 1 (Materials & Components)
    
    db.session.commit()
    
    flash('BOM item added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=1))


@bp.route('/bom/delete/<int:bom_id>')
@login_required
@permission_required('product_dev', action='delete')
def delete_bom(bom_id):
    """Delete BOM item"""
    bom_item = PDProjectBOM.query.get_or_404(bom_id)
    project_id = bom_item.project_id
    
    db.session.delete(bom_item)
    db.session.commit()
    
    flash('BOM item deleted!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=1))


# ==================== PHASE 1: MATERIALS & COMPONENTS ====================

@bp.route('/component/add/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_component(project_id):
    """Add component"""
    project = PDProject.query.get_or_404(project_id)
    
    component = PDComponent(
        project_id=project_id,
        component_name=request.form.get('component_name'),
        component_type=request.form.get('component_type'),
        quantity=float(request.form.get('quantity') or 1),
        vendor_id=request.form.get('vendor_id') or None,
        estimated_cost=float(request.form.get('estimated_cost') or 0),
        notes=request.form.get('notes')
    )
    db.session.add(component)
    
    # Keep in Phase 1 (Materials & Components)
    
    db.session.commit()
    
    flash('Component added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=2))


@bp.route('/component/delete/<int:comp_id>')
@login_required
@permission_required('product_dev', action='delete')
def delete_component(comp_id):
    """Delete component"""
    component = PDComponent.query.get_or_404(comp_id)
    project_id = component.project_id
    
    db.session.delete(component)
    db.session.commit()
    
    flash('Component deleted!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=2))


@bp.route('/component/create-po/<int:comp_id>')
@login_required
@permission_required('product_dev', action='add')
def create_purchase_order_from_component(comp_id):
    """Create Purchase Order from BUY/OUTSOURCE component"""
    component = PDComponent.query.get_or_404(comp_id)
    
    if component.component_type == 'MAKE':
        flash('Cannot create PO for MAKE components!', 'error')
        return redirect(url_for('product_development.view', project_id=component.project_id, phase=2))
    
    if not component.vendor_id:
        flash('Please select a vendor first!', 'error')
        return redirect(url_for('product_development.view', project_id=component.project_id, phase=2))
    
    # Generate PO number
    year = datetime.now().year
    prefix = f"PO-PD-{year}-"
    last_po = PurchaseOrder.query.filter(
        PurchaseOrder.po_number.like(f"{prefix}%")
    ).order_by(PurchaseOrder.po_number.desc()).first()
    
    if last_po:
        try:
            last_num = int(last_po.po_number.split('-')[-1])
            new_num = last_num + 1
        except:
            new_num = 1
    else:
        new_num = 1
    
    po = PurchaseOrder(
        po_number=f"{prefix}{new_num:04d}",
        vendor_id=component.vendor_id,
        status='Draft',
        notes=f"PD Project: {component.project.pdv_code} - {component.component_name}"
    )
    db.session.add(po)
    db.session.commit()
    
    # Link component to PO
    component.purchase_order_id = po.id
    db.session.commit()
    
    flash(f'Purchase Order {po.po_number} created!', 'success')
    return redirect(url_for('purchase.po_detail', id=po.id))


@bp.route('/component/create-mo/<int:comp_id>')
@login_required
@permission_required('product_dev', action='add')
def create_manufacturing_order_from_component(comp_id):
    """Create Manufacturing Order from MAKE component"""
    component = PDComponent.query.get_or_404(comp_id)
    
    if component.component_type != 'MAKE':
        flash('Only MAKE components can be converted to Manufacturing Orders!', 'error')
        return redirect(url_for('product_development.view', project_id=component.project_id))
    
    # Check if there's already an MO linked
    if component.manufacturing_order_id:
        flash('This component already has a Manufacturing Order linked!', 'warning')
        return redirect(url_for('product_development.view', project_id=component.project_id))
    
    project = component.project
    
    # Get or create a BOM
    from app.models import BOM, BOMItem, Company
    
    if project.sku_id:
        # Try to find existing BOM for this SKU
        bom = BOM.query.filter_by(product_id=project.sku_id, is_active=True).first()
        if not bom:
            # Create a simple BOM from PD BOM items
            bom = BOM(
                name=f"{project.product_name} - BOM",
                product_id=project.sku_id,
                version='v1',
                is_active=True
            )
            db.session.add(bom)
            db.session.commit()
            
            # Add items from PD BOM
            for pd_item in project.bom_items:
                if pd_item.sku_id:
                    item = BOMItem(
                        bom_id=bom.id,
                        component_id=pd_item.sku_id,
                        quantity=pd_item.quantity_per_unit,
                        unit_cost=pd_item.estimated_cost
                    )
                    db.session.add(item)
            db.session.commit()
    else:
        flash('Cannot create MO: Please link a product SKU to this PD project first!', 'error')
        return redirect(url_for('product_development.view', project_id=component.project_id))
    
    # Generate MO number using company settings
    company = Company.query.first()
    prefix = company.mo_prefix if company and company.mo_prefix else 'MO-'
    suffix = company.mo_suffix if company and company.mo_suffix else ''
    next_num = company.next_mo_number if company and company.next_mo_number else 1

    order_number = f"{prefix}{next_num:03d}{suffix}"
    company.next_mo_number = next_num + 1

    # Safety check for duplicates
    while ManufacturingOrder.query.filter_by(order_number=order_number).first():
        next_num += 1
        order_number = f"{prefix}{next_num:03d}{suffix}"
        company.next_mo_number = next_num + 1

    mo = ManufacturingOrder(
        order_number=order_number,
        bom_id=bom.id,
        status='Draft',
        quantity_to_produce=component.quantity,
        start_date=datetime.now().date()
    )
    db.session.add(mo)
    db.session.commit()
    
    # Link component to MO
    component.manufacturing_order_id = mo.id
    db.session.commit()
    
    flash(f'Manufacturing Order {mo.order_number} created for this PD component!', 'success')
    return redirect(url_for('product_development.view', project_id=project.id, phase=2))


# ==================== PHASE 3: TOOLING ====================

@bp.route('/tooling/add/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_tooling(project_id):
    """Add tooling"""
    project = PDProject.query.get_or_404(project_id)
    
    tooling = PDTooling(
        project_id=project_id,
        tool_name=request.form.get('tool_name'),
        tool_type=request.form.get('tool_type'),
        quantity=float(request.form.get('quantity') or 1),
        vendor_id=request.form.get('vendor_id') or None,
        cost=float(request.form.get('cost') or 0),
        status='Planned',
        expected_completion=datetime.strptime(request.form.get('expected_completion'), '%Y-%m-%d').date() if request.form.get('expected_completion') else None,
        notes=request.form.get('notes')
    )
    db.session.add(tooling)
    db.session.commit()
    
    flash('Tooling added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=2))


@bp.route('/tooling/delete/<int:tool_id>')
@login_required
@permission_required('product_dev', action='delete')
def delete_tooling(tool_id):
    """Delete tooling"""
    tooling = PDTooling.query.get_or_404(tool_id)
    project_id = tooling.project_id
    
    db.session.delete(tooling)
    db.session.commit()
    
    flash('Tooling deleted!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=2))


@bp.route('/tooling/update-status/<int:tool_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def update_tooling_status(tool_id):
    """Update tooling status"""
    tooling = PDTooling.query.get_or_404(tool_id)
    tooling.status = request.form.get('status')
    
    if tooling.status == 'Completed':
        tooling.actual_completion = datetime.now().date()
    
    db.session.commit()
    flash('Tooling status updated!', 'success')
    return redirect(url_for('product_development.view', project_id=tooling.project_id, phase=2))


@bp.route('/tooling/create-po/<int:tool_id>')
@login_required
@permission_required('product_dev', action='add')
def create_po_from_tooling(tool_id):
    """Create Purchase Order from tooling"""
    tooling = PDTooling.query.get_or_404(tool_id)
    
    if not tooling.vendor_id:
        flash('Please select a vendor first!', 'error')
        return redirect(url_for('product_development.view', project_id=tooling.project_id, phase=2))
    
    # Generate PO number
    year = datetime.now().year
    prefix = f"PO-TL-{year}-"
    last_po = PurchaseOrder.query.filter(
        PurchaseOrder.po_number.like(f"{prefix}%")
    ).order_by(PurchaseOrder.po_number.desc()).first()
    
    if last_po:
        try:
            last_num = int(last_po.po_number.split('-')[-1])
            new_num = last_num + 1
        except:
            new_num = 1
    else:
        new_num = 1
    
    po = PurchaseOrder(
        po_number=f"{prefix}{new_num:04d}",
        vendor_id=tooling.vendor_id,
        status='Draft',
        notes=f"Tooling: {tooling.tool_name} - PD: {tooling.project.pdv_code}",
        total=tooling.cost
    )
    db.session.add(po)
    db.session.commit()
    
    tooling.purchase_order_id = po.id
    db.session.commit()
    
    flash(f'Purchase Order {po.po_number} created!', 'success')
    return redirect(url_for('purchase.po_detail', id=po.id))


# ==================== PHASE 4: TESTING ====================

@bp.route('/testing/add/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_testing(project_id):
    """Add testing/trial"""
    project = PDProject.query.get_or_404(project_id)
    
    # Get next trial number
    last_trial = PDTesting.query.filter_by(project_id=project_id).order_by(PDTesting.trial_number.desc()).first()
    trial_num = (last_trial.trial_number + 1) if last_trial else 1
    
    testing = PDTesting(
        project_id=project_id,
        trial_number=trial_num,
        trial_date=datetime.strptime(request.form.get('trial_date'), '%Y-%m-%d').date() if request.form.get('trial_date') else None,
        quantity_produced=float(request.form.get('quantity_produced') or 0),
        rejected_quantity=float(request.form.get('rejected_quantity') or 0),
        test_type=request.form.get('test_type'),
        result='PENDING',
        notes=request.form.get('notes'),
        created_by=current_user.id
    )
    db.session.add(testing)
    db.session.commit()
    
    flash(f'Trial T{ trial_num } added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=3))


@bp.route('/testing/update-result/<int:test_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def update_testing_result(test_id):
    """Update testing result (PASS/FAIL)"""
    testing = PDTesting.query.get_or_404(test_id)
    testing.result = request.form.get('result')
    db.session.commit()
    
    flash(f'Testing result updated to { testing.result }!', 'success')
    return redirect(url_for('product_development.view', project_id=testing.project_id, phase=3))


@bp.route('/testing/delete/<int:test_id>')
@login_required
@permission_required('product_dev', action='delete')
def delete_testing(test_id):
    """Delete testing record"""
    testing = PDTesting.query.get_or_404(test_id)
    project_id = testing.project_id
    
    db.session.delete(testing)
    db.session.commit()
    
    flash('Testing record deleted!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=3))


# ==================== PHASE 5: APPROVAL ====================

@bp.route('/approval/update/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def update_approval(project_id):
    """Update approval status"""
    project = PDProject.query.get_or_404(project_id)
    
    approval = project.approval
    if not approval:
        approval = PDApproval(project_id=project_id)
        db.session.add(approval)
    
    approval.approval_status = request.form.get('approval_status')
    approval.approved_by = current_user.id if approval.approval_status in ['Approved', 'Rejected'] else None
    approval.approval_date = datetime.utcnow() if approval.approval_status in ['Approved', 'Rejected'] else None
    approval.remarks = request.form.get('remarks')
    invalid_expense = project_has_invalid_expenses(project)
    if invalid_expense:
        flash(f'Cannot update approval: {invalid_expense}', 'error')
        return redirect(url_for('product_development.view', project_id=project_id, phase=4))

    db.session.commit()
    
    flash('Approval status updated!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=4))


@bp.route('/sample/add/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_sample(project_id):
    project = PDProject.query.get_or_404(project_id)

    sample = ProductSample(
        project_id=project_id,
        sample_code=request.form.get('sample_code'),
        received=bool(request.form.get('received')),
        received_date=datetime.strptime(request.form.get('received_date'), '%Y-%m-%d').date() if request.form.get('received_date') else None,
        source=request.form.get('source'),
        condition=request.form.get('condition'),
        quantity=float(request.form.get('quantity') or 0),
        storage_location=request.form.get('storage_location'),
        returned=bool(request.form.get('returned')),
        notes=request.form.get('notes')
    )
    db.session.add(sample)
    db.session.commit()
    log_activity('Product Development', f'Added sample {sample.sample_code or sample.id} for {project.pdv_code}')
    flash('Sample record added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=1))


@bp.route('/reverse-engineering/update/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def update_reverse_engineering(project_id):
    project = PDProject.query.get_or_404(project_id)
    record = ProductReverseEngineering.query.filter_by(project_id=project_id).first()
    if not record:
        record = ProductReverseEngineering(project_id=project_id)
        db.session.add(record)

    record.teardown_completed = bool(request.form.get('teardown_completed'))
    record.measured_by = request.form.get('measured_by')
    record.measurement_method = request.form.get('measurement_method')
    record.critical_dimensions_recorded = bool(request.form.get('critical_dimensions_recorded'))
    record.tolerance_defined = bool(request.form.get('tolerance_defined'))
    record.material_identified = bool(request.form.get('material_identified'))
    record.bearings_seals_identified = bool(request.form.get('bearings_seals_identified'))
    record.weight_recorded = bool(request.form.get('weight_recorded'))
    record.fitment_verified = bool(request.form.get('fitment_verified'))
    record.notes = request.form.get('notes')
    db.session.commit()
    log_activity('Product Development', f'Updated reverse engineering for {project.pdv_code}')
    flash('Reverse engineering updated!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=2))


@bp.route('/drawing/add/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_drawing(project_id):
    project = PDProject.query.get_or_404(project_id)
    drawing = ProductDrawing(
        project_id=project_id,
        drawing_required_2d=bool(request.form.get('drawing_required_2d')),
        drawing_required_3d=bool(request.form.get('drawing_required_3d')),
        drawing_number=request.form.get('drawing_number'),
        drawing_revision=request.form.get('drawing_revision'),
        drawing_status=request.form.get('drawing_status') or 'Draft',
        prepared_by=request.form.get('prepared_by') or None,
        checked_by=request.form.get('checked_by') or None,
        approved_by=request.form.get('approved_by') or None,
        file_path=request.form.get('file_path'),
        revision_notes=request.form.get('revision_notes')
    )
    db.session.add(drawing)
    db.session.commit()
    log_activity('Product Development', f'Added drawing {drawing.drawing_number or drawing.id} for {project.pdv_code}')
    flash('Drawing record added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=2))


@bp.route('/tooling-trial/add/<int:tooling_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_tooling_trial(tooling_id):
    tooling = PDTooling.query.get_or_404(tooling_id)
    last_trial = ProductToolingTrial.query.filter_by(tooling_id=tooling_id).order_by(ProductToolingTrial.trial_number.desc()).first()
    trial_num = (last_trial.trial_number + 1) if last_trial else 1
    trial = ProductToolingTrial(
        project_id=tooling.project_id,
        tooling_id=tooling_id,
        trial_number=trial_num,
        trial_date=datetime.strptime(request.form.get('trial_date'), '%Y-%m-%d').date() if request.form.get('trial_date') else None,
        result=request.form.get('result') or 'PENDING',
        notes=request.form.get('notes')
    )
    db.session.add(trial)
    db.session.commit()
    log_activity('Product Development', f'Added tooling trial T{trial_num} for {tooling.tool_name}')
    flash('Tooling trial added!', 'success')
    return redirect(url_for('product_development.view', project_id=tooling.project_id, phase=2))


@bp.route('/prototype/add/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_prototype(project_id):
    project = PDProject.query.get_or_404(project_id)
    prototype = ProductPrototypeBatch(
        project_id=project_id,
        batch_code=request.form.get('batch_code'),
        batch_date=datetime.strptime(request.form.get('batch_date'), '%Y-%m-%d').date() if request.form.get('batch_date') else None,
        material_used=request.form.get('material_used'),
        prototype_cost=float(request.form.get('prototype_cost') or 0),
        assembly_cost=float(request.form.get('assembly_cost') or 0),
        testing_status=request.form.get('testing_status') or 'Pending',
        notes=request.form.get('notes')
    )
    db.session.add(prototype)
    db.session.commit()
    log_activity('Product Development', f'Added prototype batch {prototype.batch_code or prototype.id} for {project.pdv_code}')
    flash('Prototype batch added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=4))


@bp.route('/expense/add/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_expense(project_id):
    project = PDProject.query.get_or_404(project_id)
    tooling_id = request.form.get('tooling_id') or None
    prototype_batch_id = request.form.get('prototype_batch_id') or None
    work_order_id = request.form.get('work_order_id') or None
    amortization_selected = bool(request.form.get('amortization_selected'))
    expected_recovery_quantity = float(request.form.get('expected_recovery_quantity') or 0)
    category = request.form.get('expense_category')
    validation_error = validate_pd_expense(
        project_id,
        tooling_id,
        category,
        request.form.get('item_code'),
        work_order_id,
        request.form.get('cost_center'),
        amortization_selected,
        expected_recovery_quantity
    )
    if validation_error:
        flash(validation_error, 'error')
        return redirect(url_for('product_development.view', project_id=project_id, phase=4))

    expense = ProductDevelopmentExpense(
        project_id=project_id,
        tooling_id=tooling_id,
        prototype_batch_id=prototype_batch_id,
        item_code=request.form.get('item_code'),
        work_order_id=work_order_id,
        expense_category=category,
        amount=float(request.form.get('amount') or 0),
        cost_center=request.form.get('cost_center'),
        description=request.form.get('description'),
        amortization_selected=amortization_selected,
        expected_recovery_quantity=expected_recovery_quantity,
        shared_cost=bool(request.form.get('shared_cost'))
    )
    db.session.add(expense)
    db.session.commit()
    log_activity('Product Development', f'Added expense {category} for {project.pdv_code}')
    flash('Development expense added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=4))


@bp.route('/shared-allocation/add/<int:expense_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_shared_allocation(expense_id):
    expense = ProductDevelopmentExpense.query.get_or_404(expense_id)
    allocation_amount = float(request.form.get('allocated_amount') or 0)
    allocation_percent = float(request.form.get('allocation_percent') or 0)
    allocation_project_id = request.form.get('allocated_project_id')
    allocation = SharedCostAllocation(
        expense_id=expense.id,
        allocated_project_id=allocation_project_id,
        allocation_percent=allocation_percent,
        allocated_amount=allocation_amount,
        reason=request.form.get('reason')
    )
    db.session.add(allocation)
    db.session.commit()
    flash('Cost allocation added!', 'success')
    return redirect(url_for('product_development.view', project_id=expense.project_id, phase=4))


@bp.route('/attachment/add/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_attachment(project_id):
    project = PDProject.query.get_or_404(project_id)
    attachment = ProductAttachment(
        project_id=project_id,
        attachment_type=request.form.get('attachment_type'),
        file_path=request.form.get('file_path'),
        uploaded_by=current_user.id,
        notes=request.form.get('notes')
    )
    db.session.add(attachment)
    db.session.commit()
    flash('Attachment added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=4))


@bp.route('/stage/update/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def update_stage(project_id):
    project = PDProject.query.get_or_404(project_id)
    project.project_stage = request.form.get('project_stage') or project.project_stage
    project.next_action = request.form.get('next_action') or project.next_action
    db.session.commit()
    flash('Project workflow stage updated!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id))


# ==================== PHASE 6: PRODUCTION ACTIVATION ====================

@bp.route('/activate/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def activate_production(project_id):
    """Activate production - finalize BOM and mark product as production ready"""
    project = PDProject.query.get_or_404(project_id)
    
    invalid_expense = project_has_invalid_expenses(project)
    if invalid_expense:
        flash(f'Cannot activate production until invalid expenses are corrected: {invalid_expense}', 'error')
        return redirect(url_for('product_development.view', project_id=project_id, phase=5))

    # Check approval status
    if not project.approval or project.approval.approval_status != 'Approved':
        flash('Project must be approved before activating production!', 'error')
        return redirect(url_for('product_development.view', project_id=project_id, phase=5))
    
    # Update project status
    project.status = 'Completed'
    project.current_phase = 5
    
    # Create assets from completed tooling
    for tooling in project.tooling:
        if tooling.status == 'Completed':
            # Check if asset already exists
            existing_asset = PDAsset.query.filter_by(tooling_id=tooling.id).first()
            if not existing_asset:
                asset = PDAsset(
                    project_id=project.id,
                    tooling_id=tooling.id,
                    asset_name=tooling.tool_name,
                    asset_tag=generate_asset_tag(),
                    value=tooling.cost,
                    useful_life_years=5,
                    is_activated=True
                )
                db.session.add(asset)
    
    # Update linked SKU to production ready
    if project.sku:
        project.sku.is_manufactured = True
    
    db.session.commit()
    
    flash(f'Project { project.pdv_code } activated for production!', 'success')
    return redirect(url_for('product_development.view', project_id=project.id))


@bp.route('/asset/add/<int:project_id>', methods=['POST'])
@login_required
@permission_required('product_dev', action='add')
def add_asset(project_id):
    """Add asset manually"""
    project = PDProject.query.get_or_404(project_id)
    
    asset = PDAsset(
        project_id=project_id,
        tooling_id=request.form.get('tooling_id') or None,
        asset_name=request.form.get('asset_name'),
        asset_tag=generate_asset_tag(),
        value=float(request.form.get('value') or 0),
        useful_life_years=int(request.form.get('useful_life_years') or 5),
        depreciation_method=request.form.get('depreciation_method'),
        notes=request.form.get('notes')
    )
    db.session.add(asset)
    db.session.commit()
    
    flash('Asset added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=5))


@bp.route('/asset/delete/<int:asset_id>')
@login_required
@permission_required('product_dev', action='delete')
def delete_asset(asset_id):
    """Delete asset"""
    asset = PDAsset.query.get_or_404(asset_id)
    project_id = asset.project_id
    
    db.session.delete(asset)
    db.session.commit()
    
    flash('Asset deleted!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=5))


@bp.route('/asset/activate/<int:asset_id>')
@login_required
@permission_required('product_dev', action='edit')
def activate_asset(asset_id):
    """Activate an asset"""
    asset = PDAsset.query.get_or_404(asset_id)
    asset.is_activated = True
    db.session.commit()
    
    flash('Asset activated!', 'success')
    return redirect(url_for('product_development.view', project_id=asset.project_id, phase=5))


# ==================== AJAX API ====================

@bp.route('/api/bom/sku-cost/<int:sku_id>')
@login_required
def api_bom_sku_cost(sku_id):
    """Return cost price for a product/SKU for BOM auto-fill."""
    from app.models import Product
    
    try:
        product = Product.query.get_or_404(sku_id)
        cost = product.cost_price or 0
        return jsonify({'ok': True, 'cost': float(cost)})
    except Exception:
        return jsonify({'ok': False, 'cost': 0}), 200




@bp.route('/api/stats')
@login_required
def api_stats():
    """Get dashboard stats as JSON"""
    projects = PDProject.query.all()
    
    stats = {
        'total_projects': len(projects),
        'active_projects': len([p for p in projects if p.status == 'Active']),
        'completed_projects': len([p for p in projects if p.status == 'Completed']),
        'draft_projects': len([p for p in projects if p.status == 'Draft']),
        'delayed_projects': len([p for p in projects if p.is_delayed]),
        'total_investment': sum(p.total_investment for p in projects)
    }
    
    return jsonify(stats)


@bp.route('/api/project/<int:project_id>')
@login_required
def api_project(project_id):
    """Get project details as JSON"""
    project = PDProject.query.get_or_404(project_id)

    
    return jsonify({
        'id': project.id,
        'pdv_code': project.pdv_code,
        'product_name': project.product_name,
        'status': project.status,
        'current_phase': project.current_phase,
        'phase_name': project.phase_name,
        'total_investment': project.total_investment,
        'budget': project.budget,
        'approved_budget': project.approved_budget,
        'oem_part_number': project.oem_part_number,
        'aftermarket_part_number': project.aftermarket_part_number,
        'vehicle_application': project.vehicle_application,
        'requested_by': project.requested_by,
        'project_owner_id': project.project_owner_id,
        'target_market': project.target_market,
        'expected_monthly_demand': project.expected_monthly_demand,
        'target_selling_price': project.target_selling_price,
        'bom_count': len(project.bom_items),
        'component_count': len(project.components),
        'tooling_count': len(project.tooling),
        'expense_count': len(project.development_expenses),
        'attachment_count': len(project.attachments),
        'revision_count': len(project.revision_history),
        'sample_count': len(project.samples),
        'release_count': len(project.release_records),
        'budget_vs_actual': project.budget_vs_actual,
        'start_date': project.start_date.isoformat() if project.start_date else None,
        'promise_date': project.promise_date.isoformat() if project.promise_date else None,
        'is_delayed': project.is_delayed
    })


@bp.route('/phase/complete/<int:project_id>/<int:phase>', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def complete_phase(project_id, phase):
    """Complete current phase and move to next"""
    project = PDProject.query.get_or_404(project_id)
    
    # Validate phase completion requirements
    if phase == 1 and (not project.bom_items and not project.components):
        flash('Add at least one material or component before completing Phase 1', 'error')
        return redirect(url_for('product_development.view', project_id=project_id))
    
    if phase == 2 and not project.tooling:
        flash('Add at least one tooling before completing Phase 2', 'error')
        return redirect(url_for('product_development.view', project_id=project_id))
    
    if phase == 3 and project.tooling and all(t.status != 'Completed' for t in project.tooling):
        flash('Complete all tooling before completing Phase 3', 'error')
        return redirect(url_for('product_development.view', project_id=project_id))
    
    # Move to next phase if not at max
    if project.current_phase < 5:
        project.current_phase += 1
    db.session.commit()
    
    flash(f'Phase {phase} completed! Moved to Phase {project.current_phase}', 'success')
    return redirect(url_for('product_development.view', project_id=project_id))


@bp.route('/update-phase/<int:project_id>/<int:phase>', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def update_phase(project_id, phase):
    """Update project current phase"""
    project = PDProject.query.get_or_404(project_id)

    project.current_phase = phase
    db.session.commit()
    
    return jsonify({'success': True, 'phase': phase})


# Import models at the end to avoid circular imports
from app.models import (
    PDProject, PDProjectBOM, PDComponent, PDTooling, PDTesting, 
    PDApproval, PDAsset, Product, Vendor, PurchaseOrder, ManufacturingOrder,
    ProductSample, ProductReverseEngineering, ProductDrawing, ProductToolingTrial,
    ProductPrototypeBatch, ProductDevelopmentExpense, ProductBOMVersion,
    ProductRelease, ProductRevisionHistory, SharedCostAllocation, ProductAttachment,
    ProductCategory, User
)