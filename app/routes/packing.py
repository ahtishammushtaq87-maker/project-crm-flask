"""Packing Slips — a standalone, price-free module for warehouse/dispatch staff.

Deliberately separate from the Sales module. The same packing slip that can be
raised from the invoice detail page is raised here instead, from a list of
invoices that shows quantities, customers and dispatch state but NEVER any
monetary figure (no unit price, total, paid, balance, discount or tax). That
lets a packer be given access to the shipping workflow without ever being
shown what the order is worth.

The slip itself — its model, numbering and PDF — is shared with the Sales
module rather than duplicated, so a slip raised here is the same record, with
the same PKG- sequence, as one raised from the invoice page.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from datetime import datetime, date

from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.utils import permission_required, log_activity
from app.models import (
    Sale, SaleItem, Customer, CustomerGroup, Salesman, Company, PackingSlip, Warehouse
)
from app.pdf_utils import generate_packing_slip_pdf
from app.routes.filters import apply_saved_filter_to_query
# Numbering/parsing helpers live with the original implementation in the Sales
# module — imported rather than copied so both entry points can never drift
# into issuing conflicting slip numbers.
from app.routes.sales import (
    _packing_slip_settings,
    _format_packing_slip_number,
    _parse_form_date,
    _parse_form_float,
    _parse_form_int,
    _remaining_packable_qty,
)

bp = Blueprint('packing', __name__)


# ── Status expressions, mirrored from sales.invoices ──────────────────────
# A Sale is "cancelled" when is_rejected is set with this exact reason (the
# Sale status enum has no 'cancelled' member, so cancel reuses rejection).
CANCELLED_REASON = 'Cancelled by Admin'


def _not_cancelled():
    return (
        (Sale.is_rejected == False) |
        (Sale.rejection_reason.is_(None)) |
        (Sale.rejection_reason != CANCELLED_REASON)
    )


def _packable_invoices_query():
    """Invoices a packer is allowed to work from: everything except drafts,
    cancelled and rejected orders — you cannot ship what was never confirmed."""
    return Sale.query.filter(
        _not_cancelled(),
        Sale.is_draft == False,
        Sale.is_rejected == False,
    )


def _sale_warehouses(sale):
    """Comma-joined distinct warehouse names drawn on by a sale's line items,
    for display only — a single invoice can ship out of more than one
    warehouse. '-' when no item has a warehouse set.

    SaleItem only stores warehouse_id (no ORM relationship on that model), so
    each id is looked up via the session's identity map — repeat ids across
    a sale's items, or across a page of many sales sharing one warehouse,
    resolve from cache rather than re-querying."""
    names = []
    seen_ids = set()
    for item in sale.items:
        if not item.warehouse_id or item.warehouse_id in seen_ids:
            continue
        seen_ids.add(item.warehouse_id)
        wh = db.session.get(Warehouse, item.warehouse_id)
        if wh:
            names.append(wh.name)
    return ', '.join(names) if names else '-'


def _slip_defaults(sale):
    """Auto-computed prefill for the create-slip modal: the REMAINING
    packable qty (invoice total minus whatever earlier slips for this
    invoice already packed — not the invoice's flat total), and net weight
    where every product carries a weight. Quantities only — nothing here
    touches price."""
    total_qty = _remaining_packable_qty(sale)
    net_weight = 0.0
    has_weight = False
    for item in sale.items:
        product = item.product
        if product and getattr(product, 'weight', None):
            net_weight += float(item.quantity or 0) * product.weight
            has_weight = True
    return total_qty, (net_weight if has_weight else None)


def _apply_common_filters(query, args):
    """Shared filter handling for both list views. Returns the filtered query."""
    search = args.get('search', '')
    invoice_number = args.get('invoice_number')
    customer_id = args.get('customer_id', type=int)
    customer_group_id = args.get('customer_group_id', type=int)
    salesman_id = args.get('salesman_id', type=int)
    warehouse_id = args.get('warehouse_id', type=int)
    from_date = args.get('from_date')
    to_date = args.get('to_date')

    if invoice_number:
        query = query.filter(Sale.invoice_number == invoice_number)
    if customer_id:
        query = query.filter(Sale.customer_id == customer_id)
    if customer_group_id:
        query = query.join(Customer).filter(Customer.group_id == customer_group_id)
    if salesman_id:
        query = query.filter(Sale.salesman_id == salesman_id)
    if warehouse_id:
        query = query.filter(Sale.items.any(SaleItem.warehouse_id == warehouse_id))
    if search:
        like = f"%{search}%"
        query = query.outerjoin(Customer).filter(
            (Sale.invoice_number.ilike(like)) | (Customer.name.ilike(like))
        )
    if from_date:
        try:
            query = query.filter(Sale.date >= datetime.strptime(from_date, '%Y-%m-%d'))
        except ValueError:
            pass
    if to_date:
        try:
            end = datetime.strptime(to_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Sale.date <= end)
        except ValueError:
            pass
    return query


def _filter_dropdown_data():
    """Options for the filter bar — identical across both tabs."""
    return {
        'all_customers': Customer.query.filter_by(is_active=True).order_by(Customer.name).all(),
        'customer_groups': CustomerGroup.query.filter_by(is_active=True).order_by(CustomerGroup.name).all(),
        'salesmen': Salesman.query.filter_by(is_active=True).all(),
        'warehouses': Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all(),
        'recent_invoices': _packable_invoices_query().order_by(Sale.invoice_number.desc()).limit(1000).all(),
    }


def _date_format():
    company = Company.query.first()
    return company.date_format if company and company.date_format else '%Y-%m-%d'


def _request_filter_args():
    """The filter values echoed back into the template so the bar stays filled
    in after a search."""
    return {
        'search': request.args.get('search', ''),
        'invoice_number': request.args.get('invoice_number'),
        'customer_id': request.args.get('customer_id', type=int),
        'customer_group_id': request.args.get('customer_group_id', type=int),
        'salesman_id': request.args.get('salesman_id', type=int),
        'warehouse_id': request.args.get('warehouse_id', type=int),
        'from_date': request.args.get('from_date'),
        'to_date': request.args.get('to_date'),
    }


@bp.route('/')
@login_required
@permission_required('packing', action='view')
def index():
    """Invoice list for packing — all the Sales-invoice filters, none of the
    money. `packing_status` narrows to what still needs shipping vs what has
    already had a slip raised."""
    packing_status = request.args.get('packing_status', 'all')

    query = _apply_common_filters(_packable_invoices_query(), request.args)

    if packing_status == 'pending':
        query = query.filter(~Sale.packing_slips.any())
    elif packing_status == 'packed':
        query = query.filter(Sale.packing_slips.any())
    elif packing_status == 'partial':
        query = query.filter(Sale.packing_slips.any(PackingSlip.is_partial == True))

    query = apply_saved_filter_to_query(query, 'sale', request.args)
    sales = query.order_by(Sale.date.desc()).all()

    # Tab counts are computed off the unfiltered packable set so they stay a
    # stable overview rather than shifting with the active filter.
    base = _packable_invoices_query()
    counts = {
        'all': base.count(),
        'pending': base.filter(~Sale.packing_slips.any()).count(),
        'packed': base.filter(Sale.packing_slips.any()).count(),
        'partial': base.filter(Sale.packing_slips.any(PackingSlip.is_partial == True)).count(),
    }

    try:
        ps_settings = _packing_slip_settings()
        next_slip_number = _format_packing_slip_number(ps_settings, ps_settings.next_number)
    except SQLAlchemyError:
        db.session.rollback()
        next_slip_number = 'PKG-00001'

    # Per-invoice prefill for the shared modal, keyed by sale id.
    slip_defaults = {}
    for sale in sales:
        total_qty, net_weight = _slip_defaults(sale)
        slip_defaults[sale.id] = {
            'total_ordered_qty': f'{total_qty:.2f}' if total_qty else '',
            'net_weight': f'{net_weight:.2f}' if net_weight else '',
        }

    return render_template(
        'packing/index.html',
        sales=sales,
        counts=counts,
        packing_status=packing_status,
        next_slip_number=next_slip_number,
        slip_defaults=slip_defaults,
        today=datetime.utcnow().strftime('%Y-%m-%d'),
        date_format=_date_format(),
        active_module='sale',
        filter_id=request.args.get('filter_id'),
        sale_warehouses=_sale_warehouses,
        **_request_filter_args(),
        **_filter_dropdown_data()
    )


@bp.route('/slips')
@login_required
@permission_required('packing', action='view')
def slips():
    """Every packing slip ever issued, newest first, with the same filter bar
    applied to the slip's parent invoice."""
    slip_query = PackingSlip.query.join(Sale, PackingSlip.sale_id == Sale.id)
    slip_query = _apply_common_filters(slip_query, request.args)

    slip_from = request.args.get('slip_from_date')
    slip_to = request.args.get('slip_to_date')
    if slip_from:
        try:
            slip_query = slip_query.filter(
                PackingSlip.packing_date >= datetime.strptime(slip_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if slip_to:
        try:
            slip_query = slip_query.filter(
                PackingSlip.packing_date <= datetime.strptime(slip_to, '%Y-%m-%d').date())
        except ValueError:
            pass

    slip_number = request.args.get('slip_number')
    if slip_number:
        slip_query = slip_query.filter(PackingSlip.slip_number.ilike(f'%{slip_number}%'))

    partial = request.args.get('partial')
    if partial == 'yes':
        slip_query = slip_query.filter(PackingSlip.is_partial == True)
    elif partial == 'no':
        slip_query = slip_query.filter(PackingSlip.is_partial == False)

    all_slips = slip_query.order_by(PackingSlip.created_at.desc()).all()

    return render_template(
        'packing/slips.html',
        slips=all_slips,
        today=datetime.utcnow().strftime('%Y-%m-%d'),
        date_format=_date_format(),
        active_module='sale',
        slip_from_date=slip_from,
        slip_to_date=slip_to,
        slip_number=slip_number,
        partial=partial,
        remaining_packable_qty=_remaining_packable_qty,
        sale_warehouses=_sale_warehouses,
        **_request_filter_args(),
        **_filter_dropdown_data()
    )


@bp.route('/invoice/<int:id>/slip', methods=['POST'])
@login_required
@permission_required('packing', action='view')
def save_slip(id):
    """Create a new packing slip, or update an existing one when `slip_id` is
    posted, then stream the PDF back. Creating needs 'add'; editing needs
    'edit' — checked separately so a packer can be allowed to raise slips
    without being able to rewrite one already issued."""
    sale = Sale.query.get_or_404(id)
    company = Company.query.first()

    edit_slip_id = _parse_form_int(request.form.get('slip_id'))
    is_partial = request.form.get('partial_shipment') == 'yes'
    redirect_to = request.form.get('next') or url_for('packing.index')

    if edit_slip_id:
        if not (current_user.role == 'admin' or getattr(current_user, 'can_edit_packing', False)):
            flash('You do not have permission to edit a packing slip.', 'danger')
            return redirect(redirect_to)
    else:
        if not (current_user.role == 'admin' or getattr(current_user, 'can_add_packing', False)):
            flash('You do not have permission to create a packing slip.', 'danger')
            return redirect(redirect_to)

    # Hard rule, enforced server-side as well as by the form's own JS: a slip
    # cannot pack more than is actually still left on the invoice — the
    # invoice's total qty minus whatever every OTHER slip for it already
    # packed, not just whatever the submitted "Total Ordered Qty" says (that
    # field is a display/prefill, not the source of truth). Checked before
    # anything touches the DB, so a rejected submission never burns a slip
    # number, and deleting a slip needs no special handling to "give back"
    # its qty — it just stops counting against this the next time round.
    requested_packed_qty = _parse_form_float(request.form.get('total_packed_qty'))
    remaining_qty = _remaining_packable_qty(sale, exclude_slip_id=edit_slip_id)
    if requested_packed_qty is not None and requested_packed_qty > remaining_qty:
        flash(f'Total Packed Qty ({requested_packed_qty:g}) cannot exceed the remaining packable '
              f'quantity ({remaining_qty:g}) for this invoice.', 'error')
        return redirect(redirect_to)

    # Retried once on a SQLAlchemyError — a stale session or a transient SQLite
    # lock under concurrent workers is recoverable by starting over on a fresh
    # connection, so tear the session down between attempts rather than rolling
    # back onto the same possibly-poisoned one.
    last_error = None
    slip = None
    for _attempt in range(2):
        try:
            if edit_slip_id:
                # Editing leaves slip_number and the settings counter alone —
                # this only rewrites the details.
                slip = PackingSlip.query.get_or_404(edit_slip_id)
                if slip.sale_id != sale.id:
                    flash('That packing slip does not belong to this invoice.', 'error')
                    return redirect(redirect_to)
            else:
                settings = _packing_slip_settings()
                slip = PackingSlip(
                    slip_number=_format_packing_slip_number(settings, settings.next_number),
                    sale_id=sale.id,
                    created_by=current_user.id,
                )
                db.session.add(slip)
                settings.next_number = (settings.next_number or 1) + 1

            slip.packing_date = _parse_form_date(request.form.get('packing_date')) or date.today()
            slip.po_number = (request.form.get('po_number') or '').strip() or None
            slip.is_partial = is_partial
            slip.partial_shipment_no = _parse_form_int(request.form.get('partial_shipment_no')) if is_partial else None
            slip.partial_shipment_total = _parse_form_int(request.form.get('partial_shipment_total')) if is_partial else None
            slip.package_count = _parse_form_int(request.form.get('package_count'))
            slip.transport_company = (request.form.get('transport_company') or '').strip() or None
            slip.bilty_no = (request.form.get('bilty_no') or '').strip() or None
            slip.tracking_no = (request.form.get('tracking_no') or '').strip() or None
            slip.vehicle_no = (request.form.get('vehicle_no') or '').strip() or None
            slip.gate_pass_no = (request.form.get('gate_pass_no') or '').strip() or None
            slip.dispatch_date = _parse_form_date(request.form.get('dispatch_date'))
            slip.total_ordered_qty = _parse_form_float(request.form.get('total_ordered_qty'))
            slip.total_packed_qty = _parse_form_float(request.form.get('total_packed_qty'))
            slip.balance_qty = _parse_form_float(request.form.get('balance_qty'))
            slip.gross_weight = _parse_form_float(request.form.get('gross_weight'))
            slip.net_weight = _parse_form_float(request.form.get('net_weight'))
            db.session.commit()
            last_error = None
            break
        except SQLAlchemyError as e:
            db.session.rollback()
            db.session.remove()
            db.engine.dispose()
            last_error = e
            slip = None
            continue

    if last_error is not None:
        print(f"Packing slip save error (after retry): {str(last_error)}")
        flash('Error saving the packing slip — please try again.', 'error')
        return redirect(redirect_to)

    log_activity(
        'Packing',
        f"{'Updated' if edit_slip_id else 'Created'} packing slip {slip.slip_number}",
        f"Invoice {sale.invoice_number or sale.id}",
    )

    try:
        buffer = generate_packing_slip_pdf(sale, company, slip)
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = (
            f'inline; filename="{slip.slip_number}_{sale.invoice_number or "packing-slip"}.pdf"')
        return response
    except Exception as e:
        print(f"Packing slip PDF generation error: {str(e)}")
        flash(f'Slip {slip.slip_number} was saved, but the PDF could not be generated: {str(e)}', 'error')
        return redirect(redirect_to)


@bp.route('/slip/<int:slip_id>/share-link')
@login_required
@permission_required('packing', action='view')
def slip_share_link(slip_id):
    """JSON endpoint backing the WhatsApp Share button — issues the slip's
    public token only when a share is actually requested, not on every page
    load (unlike embedding valid_access_token directly in the list template,
    which would silently write a token for every row on every visit)."""
    from flask import jsonify
    slip = PackingSlip.query.get_or_404(slip_id)
    url = url_for('packing.public_slip', token=slip.valid_access_token)
    return jsonify({'success': True, 'url': url})


@bp.route('/slip/<int:slip_id>/download')
@login_required
@permission_required('packing', action='view')
def download_slip(slip_id):
    """Re-download a previously issued slip."""
    slip = PackingSlip.query.get_or_404(slip_id)
    sale = Sale.query.get_or_404(slip.sale_id)
    company = Company.query.first()
    try:
        buffer = generate_packing_slip_pdf(sale, company, slip)
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = (
            f'inline; filename="{slip.slip_number}_{sale.invoice_number or "packing-slip"}.pdf"')
        return response
    except Exception as e:
        print(f"Packing slip re-download error: {str(e)}")
        flash(f'Error generating Packing Slip PDF: {str(e)}', 'error')
        return redirect(url_for('packing.slips'))


@bp.route('/public/slip/<token>')
def public_slip(token):
    """Unauthenticated PDF link for the WhatsApp share button — same
    token-expiry pattern as sales.public_invoice, scoped to this one slip."""
    slip = PackingSlip.query.filter_by(access_token=token).first_or_404()

    if slip.token_expiry and slip.token_expiry < datetime.utcnow():
        return "Link expired", 403

    sale = Sale.query.get_or_404(slip.sale_id)
    company = Company.query.first()
    try:
        buffer = generate_packing_slip_pdf(sale, company, slip)
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = (
            f'inline; filename="{slip.slip_number}_{sale.invoice_number or "packing-slip"}.pdf"')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        return f"Error generating PDF: {str(e)}", 500


@bp.route('/slip/<int:slip_id>/delete', methods=['POST'])
@login_required
@permission_required('packing', action='delete')
def delete_slip(slip_id):
    """Remove an issued slip. The PKG- counter is intentionally NOT rewound —
    slip numbers stay unique and non-reusable for audit purposes."""
    slip = PackingSlip.query.get_or_404(slip_id)
    slip_number = slip.slip_number
    redirect_to = request.form.get('next') or url_for('packing.index')
    try:
        db.session.delete(slip)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Packing slip delete error: {str(e)}")
        flash('Error deleting the packing slip — please try again.', 'error')
        return redirect(redirect_to)

    log_activity('Packing', f'Deleted packing slip {slip_number}')
    flash(f'Packing slip {slip_number} deleted.', 'success')
    return redirect(redirect_to)
