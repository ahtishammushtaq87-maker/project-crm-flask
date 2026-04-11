from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from datetime import datetime
from sqlalchemy import func, or_
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
def create():
    """Create new product development project"""
    if request.method == 'POST':
        project = PDProject(
            pdv_code=generate_pdv_code(),
            product_name=request.form.get('product_name'),
            sku_id=request.form.get('sku_id') or None,
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else None,
            promise_date=datetime.strptime(request.form.get('promise_date'), '%Y-%m-%d').date() if request.form.get('promise_date') else None,
            budget=float(request.form.get('budget') or 0),
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
    
    products = Product.query.filter_by(is_active=True).all()
    today = datetime.now().date().strftime('%Y-%m-%d')
    return render_template('product_development/create.html', products=products, today=today)


@bp.route('/view/<int:project_id>')
@login_required
def view(project_id):
    """View project details with all phases"""
    project = PDProject.query.get_or_404(project_id)
    
    products = Product.query.filter_by(is_active=True).all()
    vendors = Vendor.query.filter_by(is_active=True).all()
    today = datetime.now().date().strftime('%Y-%m-%d')
    
    return render_template('product_development/view.html', project=project, products=products, vendors=vendors, today=today)


@bp.route('/edit/<int:project_id>', methods=['GET', 'POST'])
@login_required
def edit(project_id):
    """Edit project details"""
    project = PDProject.query.get_or_404(project_id)
    
    if request.method == 'POST':
        project.product_name = request.form.get('product_name')
        project.sku_id = request.form.get('sku_id') or None
        project.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else None
        project.promise_date = datetime.strptime(request.form.get('promise_date'), '%Y-%m-%d').date() if request.form.get('promise_date') else None
        project.budget = float(request.form.get('budget') or 0)
        project.status = request.form.get('status')
        project.description = request.form.get('description')
        
        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('product_development.view', project_id=project.id))
    
    products = Product.query.filter_by(is_active=True).all()
    return render_template('product_development/edit.html', project=project, products=products)


@bp.route('/delete/<int:project_id>', methods=['POST'])
@login_required
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


# ==================== PHASE 1: BOM ====================

@bp.route('/bom/add/<int:project_id>', methods=['POST'])
@login_required
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
    db.session.commit()
    
    flash('BOM item added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=1))


@bp.route('/bom/delete/<int:bom_id>')
@login_required
def delete_bom(bom_id):
    """Delete BOM item"""
    bom_item = PDProjectBOM.query.get_or_404(bom_id)
    project_id = bom_item.project_id
    
    db.session.delete(bom_item)
    db.session.commit()
    
    flash('BOM item deleted!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=1))


# ==================== PHASE 2: COMPONENTS ====================

@bp.route('/component/add/<int:project_id>', methods=['POST'])
@login_required
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
    db.session.commit()
    
    flash('Component added!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=2))


@bp.route('/component/delete/<int:comp_id>')
@login_required
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
    return redirect(url_for('purchase.edit_order', order_id=po.id))


@bp.route('/component/create-mo/<int:comp_id>')
@login_required
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
    from app.models import BOM, BOMItem
    
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
    
    # Generate MO number
    year = datetime.now().year
    prefix = f"MO-PD-{year}-"
    last_mo = ManufacturingOrder.query.filter(
        ManufacturingOrder.order_number.like(f"{prefix}%")
    ).order_by(ManufacturingOrder.order_number.desc()).first()
    
    if last_mo:
        try:
            last_num = int(last_mo.order_number.split('-')[-1])
            new_num = last_num + 1
        except:
            new_num = 1
    else:
        new_num = 1
    
    mo = ManufacturingOrder(
        order_number=f"{prefix}{new_num:04d}",
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
    
    flash(f'Manufacturing Order {mo.order_number} created!', 'success')
    return redirect(url_for('manufacturing.view_order', order_id=mo.id))


# ==================== PHASE 3: TOOLING ====================

@bp.route('/tooling/add/<int:project_id>', methods=['POST'])
@login_required
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
    return redirect(url_for('product_development.view', project_id=project_id, phase=3))


@bp.route('/tooling/delete/<int:tool_id>')
@login_required
def delete_tooling(tool_id):
    """Delete tooling"""
    tooling = PDTooling.query.get_or_404(tool_id)
    project_id = tooling.project_id
    
    db.session.delete(tooling)
    db.session.commit()
    
    flash('Tooling deleted!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=3))


@bp.route('/tooling/update-status/<int:tool_id>', methods=['POST'])
@login_required
def update_tooling_status(tool_id):
    """Update tooling status"""
    tooling = PDTooling.query.get_or_404(tool_id)
    tooling.status = request.form.get('status')
    
    if tooling.status == 'Completed':
        tooling.actual_completion = datetime.now().date()
    
    db.session.commit()
    flash('Tooling status updated!', 'success')
    return redirect(url_for('product_development.view', project_id=tooling.project_id, phase=3))


@bp.route('/tooling/create-po/<int:tool_id>')
@login_required
def create_po_from_tooling(tool_id):
    """Create Purchase Order from tooling"""
    tooling = PDTooling.query.get_or_404(tool_id)
    
    if not tooling.vendor_id:
        flash('Please select a vendor first!', 'error')
        return redirect(url_for('product_development.view', project_id=tooling.project_id, phase=3))
    
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
    return redirect(url_for('purchase.edit_order', order_id=po.id))


# ==================== PHASE 4: TESTING ====================

@bp.route('/testing/add/<int:project_id>', methods=['POST'])
@login_required
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
    return redirect(url_for('product_development.view', project_id=project_id, phase=4))


@bp.route('/testing/update-result/<int:test_id>', methods=['POST'])
@login_required
def update_testing_result(test_id):
    """Update testing result (PASS/FAIL)"""
    testing = PDTesting.query.get_or_404(test_id)
    testing.result = request.form.get('result')
    db.session.commit()
    
    flash(f'Testing result updated to { testing.result }!', 'success')
    return redirect(url_for('product_development.view', project_id=testing.project_id, phase=4))


@bp.route('/testing/delete/<int:test_id>')
@login_required
def delete_testing(test_id):
    """Delete testing record"""
    testing = PDTesting.query.get_or_404(test_id)
    project_id = testing.project_id
    
    db.session.delete(testing)
    db.session.commit()
    
    flash('Testing record deleted!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=4))


# ==================== PHASE 5: APPROVAL ====================

@bp.route('/approval/update/<int:project_id>', methods=['POST'])
@login_required
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
    
    db.session.commit()
    
    flash('Approval status updated!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=5))


# ==================== PHASE 6: PRODUCTION ACTIVATION ====================

@bp.route('/activate/<int:project_id>', methods=['POST'])
@login_required
def activate_production(project_id):
    """Activate production - finalize BOM and mark product as production ready"""
    project = PDProject.query.get_or_404(project_id)
    
    # Check approval status
    if project.approval and project.approval.approval_status != 'Approved':
        flash('Project must be approved before activating production!', 'error')
        return redirect(url_for('product_development.view', project_id=project_id, phase=6))
    
    # Update project status
    project.status = 'Completed'
    project.current_phase = 6
    
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
    return redirect(url_for('product_development.view', project_id=project_id, phase=6))


@bp.route('/asset/delete/<int:asset_id>')
@login_required
def delete_asset(asset_id):
    """Delete asset"""
    asset = PDAsset.query.get_or_404(asset_id)
    project_id = asset.project_id
    
    db.session.delete(asset)
    db.session.commit()
    
    flash('Asset deleted!', 'success')
    return redirect(url_for('product_development.view', project_id=project_id, phase=6))


@bp.route('/asset/activate/<int:asset_id>')
@login_required
def activate_asset(asset_id):
    """Activate an asset"""
    asset = PDAsset.query.get_or_404(asset_id)
    asset.is_activated = True
    db.session.commit()
    
    flash('Asset activated!', 'success')
    return redirect(url_for('product_development.view', project_id=asset.project_id, phase=6))


# ==================== AJAX API ====================

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
        'budget_vs_actual': project.budget_vs_actual,
        'start_date': project.start_date.isoformat() if project.start_date else None,
        'promise_date': project.promise_date.isoformat() if project.promise_date else None,
        'is_delayed': project.is_delayed
    })


@bp.route('/update-phase/<int:project_id>/<int:phase>', methods=['POST'])
@login_required
def update_phase(project_id, phase):
    """Update project current phase"""
    project = PDProject.query.get_or_404(project_id)
    project.current_phase = phase
    db.session.commit()
    
    return jsonify({'success': True, 'phase': phase})


# Import models at the end to avoid circular imports
from app.models import (
    PDProject, PDProjectBOM, PDComponent, PDTooling, PDTesting, 
    PDApproval, PDAsset, Product, Vendor, PurchaseOrder, ManufacturingOrder
)