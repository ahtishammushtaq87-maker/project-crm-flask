from flask import Blueprint, render_template, request, redirect, url_for, flash
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
    """CAN-<year>-<seq>, sequence continues across years."""
    year = datetime.now().year
    last = PDCandidate.query.order_by(PDCandidate.id.desc()).first()
    new_num = 1
    if last:
        nums = re.findall(r'\d+', last.candidate_code)
        if nums:
            new_num = int(nums[-1]) + 1
    code = f"CAN-{year}-{new_num:04d}"
    while PDCandidate.query.filter_by(candidate_code=code).first():
        new_num += 1
        code = f"CAN-{year}-{new_num:04d}"
    return code


def _active_staff():
    return Staff.query.filter_by(is_active=True).order_by(Staff.name).all()


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
    candidates = query.order_by(PDCandidate.created_at.desc()).all()

    all_candidates = PDCandidate.query.all()
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


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('product_dev', action='add')
def create():
    if request.method == 'POST':
        oem = (request.form.get('oem_part_number') or '').strip()
        name = (request.form.get('product_name') or '').strip()
        if not oem or not name:
            flash('OEM part number and candidate product are required.', 'danger')
            return redirect(url_for('pd_funnel.create'))
        dup = PDCandidate.query.filter(db.func.lower(PDCandidate.oem_part_number) == oem.lower(),
                                       PDCandidate.status.notin_(['Rejected'])).first()
        if dup and not request.form.get('confirm_duplicate'):
            flash(f'OEM part {oem} already exists as {dup.candidate_code}. Tick "create anyway" if this is a '
                  f'different saleable configuration.', 'warning')
            return render_template('product_development/funnel/form.html', candidate=None, form=request.form,
                                   staff=_active_staff(), categories=ProductCategory.query.order_by(ProductCategory.name).all(),
                                   duplicate=dup)
        candidate = PDCandidate(candidate_code=generate_candidate_code(), created_by=current_user.id)
        _fill_candidate(candidate)
        db.session.add(candidate)
        db.session.commit()
        log_activity('Product Development', f'Created funnel candidate {candidate.candidate_code}', oem)
        flash(f'Candidate {candidate.candidate_code} created. Add the three feasibility reviews next.', 'success')
        return redirect(url_for('pd_funnel.view', candidate_id=candidate.id))

    return render_template('product_development/funnel/form.html', candidate=None, form={},
                           staff=_active_staff(), categories=ProductCategory.query.order_by(ProductCategory.name).all(),
                           duplicate=None)


def _fill_candidate(c):
    c.oem_part_number = (request.form.get('oem_part_number') or '').strip()
    c.product_name = (request.form.get('product_name') or '').strip()
    c.application = request.form.get('application')
    c.product_category_id = _int('product_category_id')
    c.annual_demand = _float('annual_demand')
    c.target_price = _float('target_price')
    c.est_unit_cost = _float('est_unit_cost')
    c.owner_staff_id = _int('owner_staff_id')
    c.g1_lead_staff_id = _int('g1_lead_staff_id')
    c.g1_target_date = _date('g1_target_date')
    c.next_evidence = request.form.get('next_evidence')
    c.notes = request.form.get('notes')


@bp.route('/<int:candidate_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('product_dev', action='edit')
def edit(candidate_id):
    candidate = PDCandidate.query.get_or_404(candidate_id)
    if _locked(candidate):
        return _redirect_view(candidate.id)
    if request.method == 'POST':
        if not (request.form.get('oem_part_number') or '').strip() or not (request.form.get('product_name') or '').strip():
            flash('OEM part number and candidate product are required.', 'danger')
            return redirect(url_for('pd_funnel.edit', candidate_id=candidate.id))
        _fill_candidate(candidate)
        db.session.commit()
        log_activity('Product Development', f'Updated funnel candidate {candidate.candidate_code}')
        flash('Candidate updated.', 'success')
        return _redirect_view(candidate.id)
    return render_template('product_development/funnel/form.html', candidate=candidate, form={},
                           staff=_active_staff(), categories=ProductCategory.query.order_by(ProductCategory.name).all(),
                           duplicate=None)


@bp.route('/<int:candidate_id>/delete', methods=['POST'])
@login_required
@permission_required('product_dev', action='delete')
def delete(candidate_id):
    candidate = PDCandidate.query.get_or_404(candidate_id)
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
    return render_template('product_development/funnel/view.html', candidate=candidate,
                           staff=_active_staff(), disciplines=PD_FEASIBILITY_DISCIPLINES,
                           verdicts=REVIEW_VERDICTS, task_statuses=TASK_STATUSES,
                           decisions=GATE_DECISIONS, missing=candidate.g1_missing_items(),
                           today=datetime.now().date().strftime('%Y-%m-%d'))


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
    # One current review per discipline: supersede the previous one, keep it as history
    for r in candidate.reviews:
        if r.discipline == discipline and r.is_current:
            r.is_current = False
    review = PDFeasibilityReview(
        candidate_id=candidate.id, discipline=discipline,
        reviewer_staff_id=_int('reviewer_staff_id'),
        evidence_reference=request.form.get('evidence_reference'),
        finding=request.form.get('finding'), verdict=verdict, is_current=True,
        review_date=review_date, valid_until=valid_until, created_by=current_user.id)
    db.session.add(review)
    db.session.flush()
    _refresh_status(candidate)
    db.session.commit()
    log_activity('Product Development', f'{discipline} review ({verdict}) on {candidate.candidate_code}')
    flash(f'{discipline} review recorded.' + ('' if review.is_complete else
          ' It is incomplete (needs reviewer, evidence, finding and date) and will not count toward G1.'),
          'success' if review.is_complete else 'warning')
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
    if was_current:
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
    PD_FEASIBILITY_DISCIPLINES, PDProject, PDApproval, ProductCategory, Staff
)
