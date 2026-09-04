"""Payment management utility functions"""

from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import db
from app.models import Sale, PurchaseBill, CustomerAdvance, VendorAdvance

PAKISTAN_TZ = ZoneInfo("Asia/Karachi")


def pk_now():
    """Current Pakistan wall-clock time, independent of the server OS's own timezone (VPS hosts often default to UTC)."""
    return datetime.now(PAKISTAN_TZ).replace(tzinfo=None)


def get_working_days_in_month(year, month):
    """
    Returns the number of working days in a given month, excluding Sundays.

    Args:
        year: The year (e.g., 2026)
        month: The month (1-12)

    Returns:
        int: Number of working days (Mon-Sat), excluding all Sundays

    Examples:
        - May 2026 (31 days, 5 Sundays):   31 - 5 = 26 working days
        - June 2026 (30 days, 4 Sundays):  30 - 4 = 26 working days
        - Feb 2025 (28 days, 4 Sundays):   28 - 4 = 24 working days
    """
    _, days_in_month = monthrange(year, month)
    # weekday() returns 6 for Sunday
    sundays = sum(
        1 for day in range(1, days_in_month + 1)
        if date(year, month, day).weekday() == 6
    )
    return days_in_month - sundays


def get_required_hours_in_range(staff, start_date=None, end_date=None, hours_per_day=8):
    """
    Required attendance hours for a staff member over [start_date, end_date],
    using the same "working day" convention as get_working_days_in_month:
    every day except Sunday, minus that staff's holiday-marked attendance days.

    Defaults end_date to today and start_date to the staff's joining_date;
    if that's not set, falls back to their earliest attendance record, so an
    all-time call (no args) still spans their actual attendance history
    rather than collapsing to a single day.
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = staff.joining_date
    if start_date is None:
        earliest = min((a.date for a in staff.attendance_records), default=None)
        start_date = earliest or end_date
    if start_date > end_date:
        return 0

    holiday_dates = {
        a.date for a in staff.attendance_records
        if a.is_holiday and start_date <= a.date <= end_date
    }

    working_days = 0
    day = start_date
    one_day = timedelta(days=1)
    while day <= end_date:
        if day.weekday() != 6 and day not in holiday_dates:
            working_days += 1
        day += one_day

    return working_days * hours_per_day


def safe_update_paid_amount(model_instance, delta_amount):
    """
    Safely update paid_amount for Sale/PurchaseBill with bounds checking.
    
    Args:
        model_instance: Sale or PurchaseBill instance
        delta_amount: Amount to add/subtract (positive/negative)
    
    Returns:
        bool: True if update successful
    """
    if not isinstance(model_instance, (Sale, PurchaseBill)):
        raise ValueError("model_instance must be Sale or PurchaseBill")
    
    model_instance.paid_amount += delta_amount
    
    # Bounds checking
    if model_instance.paid_amount < 0:
        model_instance.paid_amount = 0
    if hasattr(model_instance, 'total') and model_instance.paid_amount > model_instance.total:
        model_instance.paid_amount = model_instance.total
    
    # Update status
    model_instance.update_status()

    return True


def apply_sale_payment_with_credit(sale, amount, user_id):
    """
    Apply an incoming payment amount to a Sale, capping paid_amount at the
    invoice total. Any amount beyond the invoice's balance due is converted
    into an approved CustomerAdvance for the customer, mirroring the existing
    overpayment-to-advance handling used for sale-return excess (see
    app/routes/returns.py). This makes the credit show up automatically as
    "Remaining Advance"/"Customer Remaining" on the customer profile, ledger,
    ledger PDF, and can later be applied to a future invoice.

    Args:
        sale: Sale instance being paid
        amount: Total amount received from the customer for this payment
        user_id: id of the user recording the payment (for CustomerAdvance.created_by)

    Returns:
        float: the excess amount (0 if none) converted to advance credit
    """
    balance_due = max(0.0, sale.total - sale.paid_amount)
    applied = min(amount, balance_due)
    excess = round(amount - applied, 2)

    sale.paid_amount += applied
    sale.update_status()

    if excess > 0.009 and sale.customer_id:
        advance = CustomerAdvance(
            customer_id=sale.customer_id,
            amount=excess,
            date=datetime.utcnow().date(),
            description=f"Auto-credit: overpayment on Invoice #{sale.invoice_number}",
            is_approved=True,
            created_by=user_id
        )
        db.session.add(advance)

    return excess


def apply_lump_sum_discount(sale, amount):
    """
    Give `amount` as a lump-sum discount on `sale`, spreading it across the
    invoice's items in proportion to their value.

    This is the same mechanism the "Apply Direct Discount" modal uses in
    lump_sum mode (app/routes/sales.py:apply_discount) — the discount ends up
    on the per-item columns, so totals, returns, reports and the PDF keep
    reading exactly what they read today. It is shared by the payment popups
    (invoice detail "Record Payment" and Universal Pay) so a lump-sum discount
    behaves identically wherever it is granted.

    Respects the overdue restriction: if the invoice is overdue, the customer's
    group is restricted and the override flag is not set, nothing is applied.

    Does NOT commit — the caller decides. Returns the amount actually applied
    (0 when refused or when there is nothing to spread it over).
    """
    from app.models import InvoiceSettings

    amount = round(float(amount or 0), 2)
    if amount <= 0:
        return 0.0

    # Same guard as the discount modal: an overdue invoice in a restricted
    # customer group cannot take a new discount unless explicitly overridden.
    settings = InvoiceSettings.query.first()
    rule_applies = False
    if settings and sale.customer:
        rule_applies = sale.customer.group_id in settings.restricted_group_ids
    if sale.is_overdue and not sale.ignore_overdue_discount and rule_applies:
        return 0.0

    spread_over = list(sale.items)
    if not spread_over:
        return 0.0

    weights = [((it.quantity or 0) * (it.unit_price or 0)) for it in spread_over]
    weight_total = sum(weights)

    allocated = 0.0
    for idx, item in enumerate(spread_over):
        if idx < len(spread_over) - 1:
            portion = (round(amount * weights[idx] / weight_total, 2)
                       if weight_total > 0
                       else round(amount / len(spread_over), 2))
        else:
            # Remainder lands on the last item so the parts add up exactly.
            portion = round(amount - allocated, 2)
        item.discount = (item.discount or 0) + portion
        qty = item.quantity or 0
        item.unit_discount = (item.discount / qty) if qty else 0
        allocated += portion

    sale.discount = (sale.discount or 0) + amount
    sale.calculate_totals()
    sale.update_status()
    return amount


def reverse_lump_sum_discount(sale, amount):
    """
    Undo a lump-sum discount previously granted by apply_lump_sum_discount.

    Must be called whenever the payment that carried the discount is taken
    back — deleted, rejected, or cancelled — otherwise the invoice keeps a
    discount the business never actually agreed to and its total stays
    understated forever.

    Reverses using the same value weighting the discount was spread with, and
    clamps each item so a discount can never go negative (the invoice may have
    picked up or lost other discounts in the meantime). The remainder lands on
    the last item so the parts subtract back exactly.

    Does NOT commit — the caller decides. Returns the amount actually removed.
    """
    amount = round(float(amount or 0), 2)
    if amount <= 0 or not sale:
        return 0.0

    items = list(sale.items)
    if not items:
        # Nothing to take it off individually; still correct the header figure.
        removed = min(amount, float(sale.discount or 0))
        sale.discount = max(0.0, float(sale.discount or 0) - removed)
        sale.calculate_totals()
        sale.update_status()
        return removed

    weights = [((it.quantity or 0) * (it.unit_price or 0)) for it in items]
    weight_total = sum(weights)

    removed_total = 0.0
    planned = 0.0
    for idx, item in enumerate(items):
        if idx < len(items) - 1:
            portion = (round(amount * weights[idx] / weight_total, 2)
                       if weight_total > 0
                       else round(amount / len(items), 2))
        else:
            portion = round(amount - planned, 2)
        planned += portion

        # Never drive an item's discount below zero.
        take = min(portion, float(item.discount or 0))
        if take > 0:
            item.discount = round(float(item.discount or 0) - take, 2)
            qty = item.quantity or 0
            item.unit_discount = (item.discount / qty) if qty else 0
            removed_total += take

    sale.discount = max(0.0, round(float(sale.discount or 0) - removed_total, 2))
    sale.calculate_totals()
    sale.update_status()
    return round(removed_total, 2)


def auto_apply_customer_advance(sale):
    """
    Automatically consume any available advance balance on the sale's
    customer to reduce this invoice's balance due — no manual "Apply
    Advance" click required. Mirrors the FIFO advance-consumption logic in
    app/routes/sales.py:apply_advance_to_overdue, but is not restricted to
    overdue invoices, since it's meant to run right before a payment is
    recorded so existing credit is used first.

    Args:
        sale: Sale instance a payment is about to be recorded against

    Returns:
        float: the amount of advance applied (0 if none applied)
    """
    if not sale.customer_id:
        return 0.0

    customer = sale.customer
    available_advance = customer.remaining_advance_balance
    if available_advance <= 0:
        return 0.0

    balance_due = max(0.0, sale.total - sale.paid_amount)
    if balance_due <= 0:
        return 0.0

    apply_amount = min(available_advance, balance_due)

    sale.advance_applied = (sale.advance_applied or 0) + apply_amount
    sale.paid_amount = (sale.paid_amount or 0) + apply_amount
    sale.update_status()

    # Deduct from customer advance records, oldest first
    remaining_to_apply = apply_amount
    for adv in sorted(customer.advances, key=lambda a: a.date):
        if remaining_to_apply <= 0:
            break
        available_in_adv = adv.amount - (adv.applied_amount or 0)
        if available_in_adv <= 0:
            continue
        use = min(available_in_adv, remaining_to_apply)
        adv.applied_amount = (adv.applied_amount or 0) + use
        remaining_to_apply -= use

    return apply_amount


def reverse_sale_advance_applied(sale):
    """
    Give back any customer advance credit applied to this sale — reversing
    sale.advance_applied/paid_amount and restoring the amount to the
    customer's CustomerAdvance.applied_amount records — regardless of
    whether it was applied manually, via apply_advance_to_overdue, or
    auto-applied on invoice creation/payment (auto_apply_customer_advance).

    Must be called BEFORE a Sale is deleted (see delete_invoice/
    bulk_delete_invoices in app/routes/sales.py), otherwise the applied
    amount stays permanently "used up" on the customer's advance records
    even though the invoice that used it no longer exists — understating
    their real remaining_advance_balance everywhere (customer profile,
    ledger, invoice PDF, and future auto-apply on new invoices) forever.

    Also used directly by the "Reverse Advance" button on the invoice detail
    page (app/routes/sales.py:reverse_advance_applied), for an invoice that
    isn't being deleted.

    Safe to call on a sale with no advance applied or no linked customer
    (no-op, returns 0). Does NOT call sale.update_status() or commit — the
    caller decides whether that's needed (skip it when the sale is about to
    be deleted).

    Returns:
        float: the amount reversed (0 if none)
    """
    reverse_amount = float(sale.advance_applied or 0)
    if reverse_amount <= 0 or not sale.customer_id:
        return 0.0

    customer = sale.customer
    remaining_to_reverse = reverse_amount
    for adv in sorted(customer.advances, key=lambda a: a.date):
        if remaining_to_reverse <= 0:
            break
        applied = adv.applied_amount or 0
        if applied <= 0:
            continue
        give_back = min(applied, remaining_to_reverse)
        adv.applied_amount = applied - give_back
        if adv.is_adjusted and adv.adjusted_invoice_id == sale.id:
            adv.is_adjusted = False
            adv.adjusted_invoice_id = None
        remaining_to_reverse -= give_back

    sale.advance_applied = 0
    sale.paid_amount = max(0.0, (sale.paid_amount or 0) - reverse_amount)

    return reverse_amount


def _sale_overpay_marker(sale):
    """Description used to tag CustomerAdvances that were auto-created from
    overpaying a specific sale invoice. It is the link used to find and withdraw
    that same credit again if the payment is later edited down or deleted.
    Must stay identical to the description set in apply_sale_payment_with_credit."""
    return f"Auto-credit: overpayment on Invoice #{sale.invoice_number}"


def _withdraw_sale_amount(sale, amount):
    """Withdraw `amount` of settled money from a sale, taking it out of this
    invoice's UNAPPLIED overpayment advance first (credit that never actually
    paid the invoice), then out of paid_amount. Never claws back overpayment
    credit that has already been applied to another invoice. Calls update_status."""
    remaining = round(float(amount or 0), 2)
    if remaining <= 0.009:
        sale.update_status()
        return

    if sale.customer_id:
        marker = _sale_overpay_marker(sale)
        # Query directly (not sale.customer.advances) so a credit created earlier
        # in this same session/request is seen too — the relationship cache may
        # not include it yet.
        credits = CustomerAdvance.query.filter_by(
            customer_id=sale.customer_id, description=marker
        ).filter(CustomerAdvance.is_rejected == False).all()
        # Newest credit first — undo the most recent overpayment first.
        for a in sorted(credits, key=lambda x: (x.date or datetime.min.date()), reverse=True):
            if remaining <= 0.009:
                break
            unapplied = round(float(a.amount or 0) - float(a.applied_amount or 0), 2)
            if unapplied <= 0.009:
                continue
            cut = min(unapplied, remaining)
            a.amount = round(float(a.amount or 0) - cut, 2)
            remaining = round(remaining - cut, 2)
            # Fully-consumed, never-applied credit row → drop it entirely.
            if a.amount <= 0.009 and float(a.applied_amount or 0) <= 0.009:
                db.session.delete(a)

    if remaining > 0.009:
        sale.paid_amount = max(0.0, round(float(sale.paid_amount or 0) - remaining, 2))

    sale.update_status()


def adjust_sale_payment(sale, delta, user_id):
    """Reconcile a sale after one of its payments is edited or deleted by `delta`.

    Positive delta (payment increased) settles the remaining balance and overflows
    the excess into a customer advance — exactly like recording a fresh payment.
    Negative delta (payment decreased/removed) withdraws, pulling from this
    invoice's unapplied overpayment advance first, then from paid_amount.

    This fixes the two gaps the plain paid_amount adjustment had: editing a payment
    up now routes the excess to advance (instead of just capping at the invoice
    total), and deleting an overpaying payment now fully reverses the advance it
    created. Returns the overpayment credited (0 unless delta was positive).
    """
    delta = round(float(delta or 0), 2)
    if delta > 0.009:
        return apply_sale_payment_with_credit(sale, delta, user_id)
    if delta < -0.009:
        _withdraw_sale_amount(sale, -delta)
    else:
        sale.update_status()
    return 0.0


# ─────────────────────────────────────────────────────────────────────────
# VENDOR (PURCHASE) ADVANCE HELPERS — mirror the customer/sale helpers above.
# We overpay a vendor → the excess becomes OUR prepaid credit with that vendor
# (a VendorAdvance), which then auto-applies to future bills for the vendor.
# ─────────────────────────────────────────────────────────────────────────

def apply_bill_payment_with_credit(bill, amount, user_id):
    """
    Apply an incoming payment to a PurchaseBill, capping paid_amount at the
    bill total. Any amount beyond the bill's balance is converted into an
    approved VendorAdvance for the vendor, mirroring
    apply_sale_payment_with_credit for customers. The credit then shows up as
    the vendor's remaining advance and can auto-apply to future bills.

    Args:
        bill: PurchaseBill instance being paid
        amount: Total amount paid to the vendor for this payment
        user_id: id of the user recording the payment (VendorAdvance.created_by)

    Returns:
        float: the excess amount (0 if none) converted to advance credit
    """
    # What's still owed on the bill = total minus what's paid and what was cancelled
    balance = max(0.0, bill.total - bill.paid_amount - (bill.cancelled_amount or 0))
    applied = min(amount, balance)
    excess = round(amount - applied, 2)

    bill.paid_amount += applied
    bill.update_status()

    if excess > 0.009 and bill.vendor_id:
        advance = VendorAdvance(
            vendor_id=bill.vendor_id,
            amount=excess,
            date=datetime.utcnow().date(),
            description=f"Auto-credit: overpayment on Bill #{bill.bill_number}",
            is_approved=True,
            approved_by=user_id,
            approved_at=datetime.utcnow(),
            created_by=user_id
        )
        db.session.add(advance)

    return excess


def auto_apply_vendor_advance(bill):
    """
    Automatically consume any available advance balance the business holds with
    this bill's vendor to reduce the bill's balance due — no manual "Use
    Advance" click required. Mirrors auto_apply_customer_advance; meant to run
    right after a bill is created so existing vendor credit is used first.

    Args:
        bill: PurchaseBill instance a payment/creation is being processed for

    Returns:
        float: the amount of advance applied (0 if none applied)
    """
    if not bill.vendor_id:
        return 0.0

    vendor = bill.vendor
    available_advance = vendor.remaining_advance_balance
    if available_advance <= 0:
        return 0.0

    balance = max(0.0, bill.total - bill.paid_amount - (bill.cancelled_amount or 0))
    if balance <= 0:
        return 0.0

    apply_amount = min(available_advance, balance)

    bill.advance_applied = (bill.advance_applied or 0) + apply_amount
    bill.paid_amount = (bill.paid_amount or 0) + apply_amount
    bill.update_status()

    # Deduct from vendor advance records, oldest first
    remaining_to_apply = apply_amount
    for adv in sorted(vendor.advances, key=lambda a: a.date):
        if remaining_to_apply <= 0:
            break
        available_in_adv = adv.amount - (adv.applied_amount or 0)
        if available_in_adv <= 0:
            continue
        use = min(available_in_adv, remaining_to_apply)
        adv.applied_amount = (adv.applied_amount or 0) + use
        if adv.applied_amount >= adv.amount:
            adv.is_adjusted = True
            adv.adjusted_bill_id = bill.id
        else:
            adv.adjusted_bill_id = bill.id
        remaining_to_apply -= use

    return apply_amount


def reverse_bill_advance_applied(bill):
    """
    Give back any vendor advance credit applied to this bill — reversing
    bill.advance_applied/paid_amount and restoring the amount to the vendor's
    VendorAdvance.applied_amount records (oldest first). Mirrors
    reverse_sale_advance_applied for customers.

    MUST be called BEFORE a PurchaseBill is deleted, otherwise the applied
    amount stays permanently "used up" on the vendor's advance records even
    though the bill that consumed it no longer exists — understating the
    vendor's real remaining_advance_balance everywhere (vendor profile, bill
    detail, and future auto-apply on new bills) forever.

    Safe to call on a bill with no advance applied or no linked vendor (no-op,
    returns 0). Does NOT commit — the caller decides.

    Returns:
        float: the amount reversed (0 if none)
    """
    reverse_amount = float(bill.advance_applied or 0)
    if reverse_amount <= 0 or not bill.vendor_id:
        return 0.0

    vendor = bill.vendor
    remaining_to_reverse = reverse_amount
    for adv in sorted(vendor.advances, key=lambda a: a.date):
        if remaining_to_reverse <= 0:
            break
        applied = adv.applied_amount or 0
        if applied <= 0:
            continue
        give_back = min(applied, remaining_to_reverse)
        adv.applied_amount = applied - give_back
        if adv.is_adjusted and adv.adjusted_bill_id == bill.id:
            adv.is_adjusted = False
            adv.adjusted_bill_id = None
        remaining_to_reverse -= give_back

    bill.advance_applied = 0
    bill.paid_amount = max(0.0, (bill.paid_amount or 0) - reverse_amount)

    return reverse_amount


def cleanup_linked_transactions(payment_instance):
    """
    Cleanup accounting Transactions linked to this payment.
    
    Args:
        payment_instance: Payment or BillPayment instance
    """
    from app.models import Transaction
    from sqlalchemy import or_, and_
    
    ref_type = 'payment'  # Default
    ref_id_col = None
    
    if hasattr(payment_instance, 'invoice_id'):
        ref_type = 'sale'
        ref_id_col = payment_instance.invoice_id
    elif hasattr(payment_instance, 'bill_id'):
        ref_type = 'purchase'  
        ref_id_col = payment_instance.bill_id
    
    # Delete by reference
    Transaction.query.filter(
        or_(
            and_(Transaction.reference_type == 'payment', Transaction.reference_id == payment_instance.id),
            and_(Transaction.reference_type == ref_type, Transaction.reference_id == ref_id_col, 
                 Transaction.amount == payment_instance.amount)
        )
    ).delete()


from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user

def permission_required(module, action='view'):
    """
    Decorator to check if current user has permission for a specific module and action.
    Options for action: 'view', 'add', 'edit', 'delete'.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            
            # Admins have full access
            if getattr(current_user, 'role', '') == 'admin':
                return f(*args, **kwargs)
            
            # Check specific permission
            attr_name = f'can_{action}_{module}'
            has_permission = getattr(current_user, attr_name, False)
            
            if not has_permission:
                flash(f'You do not have {action} permission for the {module} module.', 'danger')
                return redirect(request.referrer or url_for('dashboard.index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_only(f):
    """
    Decorator for routes/APIs that should be visible to admins only,
    regardless of any granular can_*_<module> permission a non-admin user
    might otherwise hold (e.g. the staff profile popup and its history
    APIs, which surface CNIC/salary/advance/company-funds detail that
    shouldn't be reachable just from can_view_salary).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if getattr(current_user, 'role', '') != 'admin':
            flash('This is only available to administrators.', 'danger')
            return redirect(request.referrer or url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function


def admin_only_api(f):
    """
    Same admin-only gate as admin_only, but for JSON endpoints called via
    fetch()/AJAX -- returns a JSON 403 instead of redirecting, since a
    redirected HTML login/dashboard page would otherwise reach the caller's
    `.then(r => r.json())` and fail confusingly.
    """
    from flask import jsonify

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'message': 'Please log in.'}), 401
        if getattr(current_user, 'role', '') != 'admin':
            return jsonify({'success': False, 'message': 'This is only available to administrators.'}), 403
        return f(*args, **kwargs)
    return decorated_function


def format_qty(value, unit=''):
    """
    Format quantity values. 
    Shows as integer if unit is pieces/pcs or if value is a whole number.
    Otherwise shows with 3 decimal places.
    """
    if value is None:
        return '0'
    
    try:
        qty = float(value)
    except (ValueError, TypeError):
        return str(value)
    
    # Check if it's a piece-like unit
    is_pieces = False
    if unit and str(unit).lower() in ['pcs', 'pieces', 'pc', 'piece']:
        is_pieces = True
    
    # Format based on unit or if it's a whole number
    if is_pieces or qty == int(qty):
        return f"{int(qty):,}"
    
    return f"{qty:,.3f}"


def sku_link(sku, product_id=None):
    """
    Render an item's SKU as a clickable trigger that opens the global
    Item History popup (the same popup used on the Inventory > Products page).

    Usable in ANY template as {{ sku_link(product.sku, product.id) }}.
    If the numeric product id is not available at the call-site, pass just the
    SKU: {{ sku_link(some_sku) }} — the popup is then resolved by SKU string.

    Returns safe HTML so it renders inline anywhere a SKU is currently shown.
    """
    from markupsafe import Markup, escape

    if sku is None or str(sku).strip() == '':
        return Markup('<span class="text-muted">-</span>')

    esc_sku = escape(str(sku).strip())

    if product_id not in (None, '', 0, '0'):
        data_attr = f'data-entity-id="{escape(str(product_id))}"'
    else:
        data_attr = f'data-entity-sku="{esc_sku}"'

    return Markup(
        '<a href="javascript:void(0)" class="entity-history-trigger sku-history-link" '
        'data-entity-type="inventory" ' + data_attr + '>' + str(esc_sku) + '</a>'
    )


def log_activity(module, action, details=None):
    """
    Log user activity to the database.
    
    Args:
        module: Name of the module (e.g., 'Sales', 'Purchase')
        action: Description of the action (e.g., 'Created Invoice #INV-001')
        details: Optional additional text details
    """
    from flask_login import current_user
    from flask import request
    from app.models import ActivityLog
    from app import db
    
    user_id = current_user.id if current_user.is_authenticated else None
    ip_address = request.remote_addr
    
    log = ActivityLog(
        user_id=user_id,
        module=module,
        action=action,
        details=details,
        ip_address=ip_address
    )
    db.session.add(log)
    try:
        db.session.commit()
    except:
        db.session.rollback()
