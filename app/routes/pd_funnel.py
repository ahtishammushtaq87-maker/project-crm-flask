from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.utils import permission_required
from flask_login import login_required, current_user
from app import db
from app.utils import log_activity
from datetime import datetime
import re

bp = Blueprint('pd_funnel', __name__, url_prefix='/product-development/funnel')

CANDIDATE_STATUSES = ['Intake', 'In Review', 'G1 Approved', 'Rejected', 'On Hold']
REVIEW_VERDICTS = ['Go', 'Conditional Go', 'No-Go']
TASK_STATUSES = ['Open', 'In Progress', 'Done']
GATE_DECISIONS = ['Approved', 'Rejected', 'On Hold']


def _date(name):
    val = request.form.get(name)
    return datetime.strptime(val, '%Y-%m-%d').date() if val else None


def _float(name):
    try:
        return float(request.form.get(name) or 0)
    except ValueError:
        return 0


def _int(name):
    val = request.form.get(name)
    return int(val) if val and val.isdigit() else None


def generate_candidate_code():
    """FN-<year>-<seq>, sequence continues across years."""
    year = datetime.now().year
    last = PDCandidate.query.order_by(PDCandidate.id.desc()).first()
    new_num = 1
    if last:
        nums = re.findall(r'\d+', last.candidate_code)
        if nums:
            new_num = int(nums[-1]) + 1
    code = f"FN-{year}-{new_num:04d}"
    while PDCandidate.query.filter_by(candidate_code=code).first():
        new_num += 1
        code = f"FN-{year}-{new_num:04d}"
    return code


def generate_funnel_number(category_id=None):
    """Auto-generate Funnel No. using category SKU prefix if available, else FN-<year>-<seq>.
    Format: <cat_prefix>-FN-<seq3> or FN-<year>-<seq4>."""
    year = datetime.now().year
    cat = ProductCategory.query.get(category_id) if category_id else None
    prefix_base = (cat.sku_prefix or '').strip() if cat else ''
    if prefix_base:
        prefix = f"{prefix_base}-FN-"
    else:
        prefix = f"FN-{year}-"
    pad = 3 if prefix_base else 4
    # Find highest existing number with this prefix
    existing = PDCandidate.query.with_entities(PDCandidate.oem_part_number).filter(
        PDCandidate.oem_part_number.like(f'{prefix}%')).all()
    highest = 0
    for (num,) in existing:
        suffix = (num or '')[len(prefix):]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    candidate_num = highest + 1
    fn = f"{prefix}{candidate_num:0{pad}d}"
    while PDCandidate.query.filter_by(oem_part_number=fn).first():
        candidate_num += 1
        fn = f"{prefix}{candidate_num:0{pad}d}"
    return fn


def _active_staff():
    return Staff.query.filter_by(is_active=True).order_by(Staff.name).all()


def _admin_users():
    from app.models import User
    return User.query.filter_by(role='admin', is_active=True).order_by(User.username).all()


def _redirect_view(candidate_id, tab=None):
    return redirect(url_for('pd_funnel.view', candidate_id=candidate_id, _anchor=tab) if tab
                    else url_for('pd_funnel.view', candidate_id=candidate_id))


def _locked(candidate):
    """Candidates with a G1 decision that created a project are read-only."""
    if candidate.project_id:
        flash('This candidate is already approved and linked to a project; it is read-only.', 'warning')
        return True
    return False


def _refresh_status(candidate):
    if candidate.status in ('G1 Approved', 'Rejected', 'On Hold'):
        return
    candidate.status = 'In Review' if (candidate.reviews or candidate.tasks) else 'Intake'


def create_project_from_candidate(candidate, gate):
    """Effective G1 -> PDV project linked to the candidate, budget capped at the G1 sample cap."""
    from app.routes.product_development import generate_pdv_code
    project = PDProject(
        pdv_code=generate_pdv_code(),
        product_name=candidate.product_name,
        product_category_id=candidate.product_category_id,
        oem_part_number=candidate.oem_part_number,
        vehicle_application=candidate.application,
        expected_monthly_demand=round((candidate.annual_demand or 0) / 12, 2),
        target_selling_price=candidate.target_price or 0,
        cost=candidate.est_unit_cost or 0,
        budget=gate.approved_cap or 0,
        approved_budget=gate.approved_cap or 0,
        start_date=datetime.now().date(),
        status='Active',
        current_phase=1,
        project_stage='Sample Required',
        next_action='Purchase OEM sample within G1 cap',
        description=(f"Created from funnel candidate {candidate.candidate_code} (G1 approved "
                     f"{gate.decision_date.strftime('%Y-%m-%d') if gate.decision_date else ''}).\n"
                     f"{candidate.notes or ''}").strip(),
        created_by=current_user.id,
    )
    db.session.add(project)
    db.session.flush()
    db.session.add(PDApproval(project_id=project.id))
    candidate.project_id = project.id
    # Transfer funnel components to the new project
    for fc in candidate.funnel_components:
        db.session.add(PDComponent(
            project_id=project.id,
            component_name=fc.component_name,
            product_id=fc.product_id,
            component_type=fc.component_type,
            quantity=fc.quantity,
            vendor_id=fc.vendor_id,
            estimated_cost=fc.estimated_cost,
            notes=fc.notes,
        ))
    return project


@bp.route('/')
@login_required
@permission_required('product_dev', action='view')
def index():
    status = request.args.get('status', '')
    q = (request.args.get('q') or '').strip()
    query = PDCandidate.query
    if status:
        query = query.filter(PDCandidate.status == status)
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(PDCandidate.candidate_code.ilike(like),
                                    PDCandidate.oem_part_number.ilike(like),
                                    PDCandidate.product_name.ilike(like)))
    # Rows with a NULL primary key come back as None; skip them instead of crashing
    candidates = [c for c in query.order_by(PDCandidate.created_at.desc()).all() if c is not None]

    all_candidates = [c for c in PDCandidate.query.all() if c is not None]
    stats = {
        'total': len(all_candidates),
        'intake': sum(1 for c in all_candidates if c.status == 'Intake'),
        'review': sum(1 for c in all_candidates if c.status == 'In Review'),
        'approved': sum(1 for c in all_candidates if c.status == 'G1 Approved'),
        'rejected': sum(1 for c in all_candidates if c.status in ('Rejected', 'On Hold')),
        'ready': sum(1 for c in all_candidates
                     if c.status in ('Intake', 'In Review') and not c.g1_missing_items()),
    }
    return render_template('product_development/funnel/index.html', candidates=candidates,
                           stats=stats, statuses=CANDIDATE_STATUSES, status=status, q=q)


@bp.route('/api/funnel-number')
@login_required
def api_funnel_number():
    """Return next funnel number for a given category (used by JS on form)."""
    cat_id = request.args.get('category_id', type=int)
    return jsonify(funnel_number=generate_funnel_number(cat_id))


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('product_dev', action='add')
def create():
    if request.method == 'POST':
        name = (request.form.get('product_name') or '').strip()
        if not name:
            flash('Candidate product name is required.', 'danger')
            return redirect(url_for('pd_funnel.create'))
        # Funnel number is auto-generated by JS and submitted as hidden field; regenerate server-side if missing
        cat_id = _int('product_category_id')
        funnel_no = (request.form.get('oem_part_number') or '').strip() or generate_funnel_number(cat_id)
        dup = PDCandidate.query.filter(db.func.lower(PDCandidate.oem_part_number) == funnel_no.lower(),
                                       PDCandidate.status.notin_(['Rejected'])).first()
        if dup and not request.form.get('confirm_duplicate'):
            flash(f'Funnel No. {funnel_no} already exists as {dup.candidate_code}. Tick "create anyway" if this is a '
                  f'different saleable configuration.', 'warning')
            return render_template('product_development/funnel/form.html', candidate=None, form=request.form,
                                   staff=_active_staff(), admins=_admin_users(),
                                   categories=ProductCategory.query.order_by(ProductCategory.name).all(),
                                   duplicate=dup)
        candidate = PDCandidate(candidate_code=generate_candidate_code(), created_by=current_user.id)
        _fill_candidate(candidate, funnel_no)
        db.session.add(candidate)
        db.session.flush()  # get candidate.id before saving VOC
        _save_voc_entries(candidate)
        db.session.commit()
        log_activity('Product Development', f'Created funnel candidate {candidate.candidate_code}', funnel_no)
        flash(f'Candidate {candidate.candidate_code} created. Add the three feasibility reviews next.', 'success')
        return redirect(url_for('pd_funnel.view', candidate_id=candidate.id))

    # Pre-generate a funnel number for display (no category selected yet)
    initial_funnel_no = generate_funnel_number(None)
    return render_template('product_development/funnel/form.html', candidate=None, form={},
                           staff=_active_staff(), admins=_admin_users(),
                           categories=ProductCategory.query.order_by(ProductCategory.name).all(),
                           duplicate=None, initial_funnel_no=initial_funnel_no)


def _fill_candidate(c, funnel_no=None):
    c.oem_part_number = funnel_no or (request.form.get('oem_part_number') or '').strip()
    c.product_name = (request.form.get('product_name') or '').strip()
    c.application = request.form.get('application')
    c.product_category_id = _int('product_category_id')
    c.annual_demand = _float('annual_demand')
    c.target_price = _float('target_price')
    c.est_unit_cost = _float('est_unit_cost')
    owner_val = (request.form.get('owner_staff_id') or '').strip()
    if owner_val.startswith('u_'):
        c.owner_staff_id = None
        c.owner_user_id = int(owner_val[2:]) if owner_val[2:].isdigit() else None
    else:
        c.owner_staff_id = int(owner_val) if owner_val.isdigit() else None
        c.owner_user_id = None
    lead_val = (request.form.get('g1_lead_staff_id') or '').strip()
    if lead_val.startswith('u_'):
        c.g1_lead_staff_id = None
        c.g1_lead_user_id = int(lead_val[2:]) if lead_val[2:].isdigit() else None
    else:
        c.g1_lead_staff_id = int(lead_val) if lead_val.isdigit() else None
        c.g1_lead_user_id = None
    c.g1_target_date = _date('g1_target_date')
    c.notes = request.form.get('notes')


def _save_voc_entries(candidate):
    """Parse voc_entries_json from the form and create PDVoiceOfCustomer records."""
    import json, os, base64, uuid
    raw = (request.form.get('voc_entries_json') or '').strip()
    if not raw or raw == '[]':
        return
    try:
        entries = json.loads(raw)
    except Exception:
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        text = (entry.get('text') or '').strip()
        if not text:
            continue
        image_path = None
        image_data = (entry.get('imageData') or '').strip()
        if image_data and image_data.startswith('data:image'):
            try:
                header, b64 = image_data.split(',', 1)
                ext = 'png'
                if 'jpeg' in header or 'jpg' in header:
                    ext = 'jpg'
                elif 'gif' in header:
                    ext = 'gif'
                elif 'webp' in header:
                    ext = 'webp'
                folder = os.path.join('app', 'static', 'uploads', 'voc_images')
                os.makedirs(folder, exist_ok=True)
                filename = f'voc_{candidate.id}_{uuid.uuid4().hex[:8]}.{ext}'
                with open(os.path.join(folder, filename), 'wb') as f:
                    f.write(base64.b64decode(b64))
                image_path = f'uploads/voc_images/{filename}'
            except Exception:
                pass
        db.session.add(PDVoiceOfCustomer(
            candidate_id=candidate.id,
            review_text=text,
            image_path=image_path,
        ))


@bp.route('/<int:candidate_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('product_dev', action='edit')
def edit(candidate_id):
    candidate = PDCandidate.query.get_or_404(candidate_id)
    if not current_user.is_admin:
        flash('Only an admin can edit a candidate.', 'danger')
        return _redirect_view(candidate.id)
    if _locked(candidate):
        return _redirect_view(candidate.id)
    if request.method == 'POST':
        if not (request.form.get('product_name') or '').strip():
            flash('Candidate product name is required.', 'danger')
            return redirect(url_for('pd_funnel.edit', candidate_id=candidate.id))
        _fill_candidate(candidate)
        _save_voc_entries(candidate)
        db.session.commit()
        log_activity('Product Development', f'Updated funnel candidate {candidate.candidate_code}')
        flash('Candidate updated.', 'success')
        return _redirect_view(candidate.id)
    return render_template('product_development/funnel/form.html', candidate=candidate, form={},
                           staff=_active_staff(), admins=_admin_users(),
                           categories=ProductCategory.query.order_by(ProductCategory.name).all(),
                           duplicate=None, initial_funnel_no=candidate.oem_part_number)


@bp.route('/<int:candidate_id>/delete', methods=['POST'])
@login_required
@permission_required('product_dev', action='delete')
def delete(candidate_id):
    candidate = PDCandidate.query.get_or_404(candidate_id)
    if not current_user.is_admin:
        flash('Only an admin can delete a candidate.', 'danger')
        return _redirect_view(candidate.id)
    if candidate.project_id:
        flash('Cannot delete a candidate that already created a project.', 'danger')
        return _redirect_view(candidate.id)
    code = candidate.candidate_code
    db.session.delete(candidate)
    db.session.commit()
    log_activity('Product Development', f'Deleted funnel candidate {code}')
    flash(f'Candidate {code} deleted.', 'success')
    return redirect(url_for('pd_funnel.index'))


@bp.route('/<int:candidate_id>')
@login_required
@permission_required('product_dev', action='view')
def view(candidate_id):
    candidate = PDCandidate.query.get_or_404(candidate_id)
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    vendors = Vendor.query.filter_by(is_active=True).order_by(Vendor.name).all()
    return render_template('product_development/funnel/view.html', candidate=candidate,
                           staff=_active_staff(), disciplines=PD_FEASIBILITY_DISCIPLINES,
                           verdicts=REVIEW_VERDICTS, task_statuses=TASK_STATUSES,
                           decisions=GATE_DECISIONS, missing=candidate.g1_missing_items(),
                           today=datetime.now().date().strftime('%Y-%m-%d'),
                           products=products, vendors=vendors)


# ---------- Feasibility reviews ----------

@bp.route('/<int:candidate_id>/review/add', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def add_review(candidate_id):
    candidate = PDCandidate.query.get_or_404(candidate_id)
    if _locked(candidate):
        return _redirect_view(candidate.id)
    discipline = request.form.get('discipline')
    verdict = request.form.get('verdict')
    if discipline not in PD_FEASIBILITY_DISCIPLINES or verdict not in REVIEW_VERDICTS:
        flash('Choose a valid discipline and verdict.', 'danger')
        return _redirect_view(candidate.id, 'reviews')
    review_date = _date('review_date')
    valid_until = _date('valid_until')
    if review_date and valid_until and valid_until < review_date:
        flash('Validity date cannot be before the review date.', 'danger')
        return _redirect_view(candidate.id, 'reviews')
    # Bulk select: one review row per reviewer, all sharing the same verdict and evidence
    reviewer_ids = list(dict.fromkeys(int(v) for v in request.form.getlist('reviewer_staff_id') if v.isdigit()))
    if not reviewer_ids:
        flash('Select at least one reviewer.', 'danger')
        return _redirect_view(candidate.id, 'reviews')
    # Current reviews per discipline: supersede the previous ones, keep them as history
    for r in candidate.reviews:
        if r.discipline == discipline and r.is_current:
            r.is_current = False
    reviews = []
    for staff_id in reviewer_ids:
        review = PDFeasibilityReview(
            candidate_id=candidate.id, discipline=discipline,
            reviewer_staff_id=staff_id,
            evidence_reference=request.form.get('evidence_reference'),
            finding=request.form.get('finding'), verdict=verdict, is_current=True,
            review_date=review_date, valid_until=valid_until, created_by=current_user.id)
        db.session.add(review)
        reviews.append(review)
    db.session.flush()
    _refresh_status(candidate)
    db.session.commit()
    log_activity('Product Development', f'{discipline} review ({verdict}) by {len(reviews)} reviewer(s) on {candidate.candidate_code}')
    complete = all(r.is_complete for r in reviews)
    flash(f'{discipline} review recorded for {len(reviews)} reviewer(s).' + ('' if complete else
          ' It is incomplete (needs reviewer, evidence, finding and date) and will not count toward G1.'),
          'success' if complete else 'warning')
    return _redirect_view(candidate.id, 'reviews')


@bp.route('/review/<int:review_id>/delete', methods=['POST'])
@login_required
@permission_required('product_dev', action='delete')
def delete_review(review_id):
    review = PDFeasibilityReview.query.get_or_404(review_id)
    candidate = review.candidate
    if _locked(candidate):
        return _redirect_view(candidate.id)
    was_current, discipline = review.is_current, review.discipline
    db.session.delete(review)
    db.session.flush()
    still_current = PDFeasibilityReview.query.filter_by(
        candidate_id=candidate.id, discipline=discipline, is_current=True).first()
    if was_current and not still_current:
        # Promote the most recent superseded review back to current
        prev = PDFeasibilityReview.query.filter_by(candidate_id=candidate.id, discipline=discipline) \
            .order_by(PDFeasibilityReview.id.desc()).first()
        if prev:
            prev.is_current = True
    db.session.commit()
    flash('Review deleted.', 'success')
    return _redirect_view(candidate.id, 'reviews')


# ---------- Stage tasks ----------

def _save_members(task):
    task.members.clear()
    staff_ids = request.form.getlist('member_staff_id')
    roles = request.form.getlist('member_role')
    seen = set()
    for i, sid in enumerate(staff_ids):
        if not sid or not sid.isdigit() or int(sid) in seen or int(sid) == task.primary_staff_id:
            continue
        seen.add(int(sid))
        task.members.append(PDTaskMember(staff_id=int(sid), role=(roles[i] if i < len(roles) else None)))


@bp.route('/<int:candidate_id>/task/add', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def add_task(candidate_id):
    candidate = PDCandidate.query.get_or_404(candidate_id)
    if _locked(candidate):
        return _redirect_view(candidate.id)
    deliverable = (request.form.get('deliverable') or '').strip()
    if not deliverable:
        flash('Deliverable is required.', 'danger')
        return _redirect_view(candidate.id, 'tasks')
    task = PDStageTask(candidate_id=candidate.id, stage='G1', deliverable=deliverable,
                       primary_staff_id=_int('primary_staff_id'), due_date=_date('due_date'),
                       status='Open')
    db.session.add(task)
    _save_members(task)
    db.session.flush()
    _refresh_status(candidate)
    db.session.commit()
    flash(f'Task {task.task_code} added.', 'success')
    return _redirect_view(candidate.id, 'tasks')


@bp.route('/task/<int:task_id>/update', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def update_task(task_id):
    task = PDStageTask.query.get_or_404(task_id)
    candidate = task.candidate
    if _locked(candidate):
        return _redirect_view(candidate.id)
    status = request.form.get('status')
    accepted = bool(request.form.get('accepted'))
    evidence = (request.form.get('evidence_reference') or '').strip()
    task.deliverable = (request.form.get('deliverable') or task.deliverable).strip()
    task.primary_staff_id = _int('primary_staff_id')
    task.due_date = _date('due_date')
    task.status = status if status in TASK_STATUSES else task.status
    task.evidence_reference = evidence
    warning = None
    if accepted and not evidence:
        # Keep the other edits; acceptance itself needs evidence
        accepted = False
        warning = 'saved, but not accepted: enter an evidence reference to accept it.'
    elif accepted and task.status != 'Done':
        # Accepting with evidence means the work is finished
        task.status = 'Done'
    task.accepted = accepted
    _save_members(task)
    db.session.commit()
    if warning:
        flash(f'Task {task.task_code} {warning}', 'warning')
    else:
        problem = task.assignment_problem
        flash(f'Task {task.task_code} updated' + (f' (still blocking G1: {problem}).' if problem else ' and ready for G1.'),
              'info' if problem else 'success')
    return _redirect_view(candidate.id, 'tasks')


@bp.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
@permission_required('product_dev', action='delete')
def delete_task(task_id):
    task = PDStageTask.query.get_or_404(task_id)
    candidate = task.candidate
    if _locked(candidate):
        return _redirect_view(candidate.id)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'success')
    return _redirect_view(candidate.id, 'tasks')


# ---------- Funnel components ----------

@bp.route('/<int:candidate_id>/component/add', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def add_funnel_component(candidate_id):
    candidate = PDCandidate.query.get_or_404(candidate_id)
    if _locked(candidate):
        return _redirect_view(candidate.id)
    product_id = request.form.get('product_id', type=int)
    product = Product.query.get(product_id) if product_id else None
    if not product:
        flash('Select an inventory item for the component.', 'danger')
        return _redirect_view(candidate.id, 'components')
    comp = PDFunnelComponent(
        candidate_id=candidate.id,
        component_name=product.name,
        product_id=product.id,
        component_type=request.form.get('component_type', 'BUY'),
        quantity=float(request.form.get('quantity') or 1),
        vendor_id=_int('vendor_id'),
        estimated_cost=_float('estimated_cost'),
        notes=request.form.get('notes'),
    )
    db.session.add(comp)
    db.session.commit()
    flash('Component added.', 'success')
    return _redirect_view(candidate.id, 'components')


@bp.route('/funnel-component/<int:comp_id>/delete', methods=['POST'])
@login_required
@permission_required('product_dev', action='delete')
def delete_funnel_component(comp_id):
    comp = PDFunnelComponent.query.get_or_404(comp_id)
    candidate = comp.candidate
    if _locked(candidate):
        return _redirect_view(candidate.id)
    db.session.delete(comp)
    db.session.commit()
    flash('Component removed.', 'success')
    return _redirect_view(candidate.id, 'components')


# ---------- Voice of Customer reviews ----------

@bp.route('/<int:candidate_id>/voc/add', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def add_voc(candidate_id):
    import os, base64, uuid
    candidate = PDCandidate.query.get_or_404(candidate_id)
    review_text = (request.form.get('review_text') or '').strip()
    if not review_text:
        flash('Review text is required.', 'danger')
        return _redirect_view(candidate.id, 'voc')
    image_path = None
    image_data = (request.form.get('voc_image_data') or '').strip()
    if image_data and image_data.startswith('data:image'):
        try:
            header, b64 = image_data.split(',', 1)
            ext = 'png'
            if 'jpeg' in header or 'jpg' in header:
                ext = 'jpg'
            elif 'gif' in header:
                ext = 'gif'
            elif 'webp' in header:
                ext = 'webp'
            folder = os.path.join('app', 'static', 'uploads', 'voc_images')
            os.makedirs(folder, exist_ok=True)
            filename = f'voc_{candidate_id}_{uuid.uuid4().hex[:8]}.{ext}'
            with open(os.path.join(folder, filename), 'wb') as f:
                f.write(base64.b64decode(b64))
            image_path = f'uploads/voc_images/{filename}'
        except Exception:
            pass
    db.session.add(PDVoiceOfCustomer(
        candidate_id=candidate.id,
        review_text=review_text,
        image_path=image_path,
    ))
    db.session.commit()
    flash('Review added.', 'success')
    return _redirect_view(candidate.id, 'voc')


@bp.route('/voc/<int:voc_id>/delete', methods=['POST'])
@login_required
@permission_required('product_dev', action='delete')
def delete_voc(voc_id):
    import os
    voc = PDVoiceOfCustomer.query.get_or_404(voc_id)
    candidate = voc.candidate
    if voc.image_path:
        try:
            os.remove(os.path.join('app', 'static', voc.image_path))
        except Exception:
            pass
    db.session.delete(voc)
    db.session.commit()
    flash('Review removed.', 'success')
    return _redirect_view(candidate.id, 'voc')


# ---------- G1 gate ----------

@bp.route('/<int:candidate_id>/gate', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def gate_decision(candidate_id):
    candidate = PDCandidate.query.get_or_404(candidate_id)
    if _locked(candidate):
        return _redirect_view(candidate.id)
    decision = request.form.get('decision')
    approver_id = _int('approver_staff_id')
    decision_date = _date('decision_date')
    evidence = (request.form.get('evidence_reference') or '').strip()
    cap = _float('approved_cap')

    if decision not in GATE_DECISIONS:
        flash('Choose a decision.', 'danger')
        return _redirect_view(candidate.id, 'gate')
    if not approver_id or not decision_date:
        flash('A signed decision needs an approver and a decision date.', 'danger')
        return _redirect_view(candidate.id, 'gate')

    if decision == 'Approved':
        missing = candidate.g1_missing_items()
        if not evidence:
            missing.append('Gate evidence reference')
        if cap <= 0:
            missing.append('Approved sample purchase cap (PKR)')
        if missing:
            flash('G1 cannot be approved yet. Missing: ' + '; '.join(missing), 'danger')
            return _redirect_view(candidate.id, 'gate')

    gate = PDGateReview(gate='G1', candidate_id=candidate.id, decision=decision,
                        approver_staff_id=approver_id, decision_date=decision_date,
                        evidence_reference=evidence, approved_cap=cap if decision == 'Approved' else 0,
                        remarks=request.form.get('remarks'), created_by=current_user.id)
    db.session.add(gate)

    if decision == 'Approved':
        candidate.status = 'G1 Approved'
        project = create_project_from_candidate(candidate, gate)
        db.session.commit()
        log_activity('Product Development',
                     f'G1 approved {candidate.candidate_code}; project {project.pdv_code} created',
                     f'Sample cap PKR {cap:,.0f}')
        flash(f'G1 approved. Project {project.pdv_code} created automatically with a PKR {cap:,.0f} sample cap.',
              'success')
        return redirect(url_for('product_development.view', project_id=project.id))

    candidate.status = 'Rejected' if decision == 'Rejected' else 'On Hold'
    db.session.commit()
    log_activity('Product Development', f'G1 {decision.lower()} for {candidate.candidate_code}')
    flash(f'G1 decision recorded: {decision}.', 'info')
    return _redirect_view(candidate.id, 'gate')


@bp.route('/<int:candidate_id>/reopen', methods=['POST'])
@login_required
@permission_required('product_dev', action='edit')
def reopen(candidate_id):
    """Bring a Rejected / On Hold candidate back into review (decision history is kept)."""
    candidate = PDCandidate.query.get_or_404(candidate_id)
    if candidate.project_id or candidate.status not in ('Rejected', 'On Hold'):
        flash('Only rejected or on-hold candidates can be reopened.', 'warning')
        return _redirect_view(candidate.id)
    candidate.status = 'In Review'
    db.session.commit()
    log_activity('Product Development', f'Reopened funnel candidate {candidate.candidate_code}')
    flash('Candidate reopened for review.', 'success')
    return _redirect_view(candidate.id)


# Import models at the end to avoid circular imports
from app.models import (
    PDCandidate, PDFeasibilityReview, PDStageTask, PDTaskMember, PDGateReview,
    PD_FEASIBILITY_DISCIPLINES, PDProject, PDApproval, PDComponent, PDFunnelComponent,
    PDVoiceOfCustomer, ProductCategory, Staff, Product, Vendor
)
