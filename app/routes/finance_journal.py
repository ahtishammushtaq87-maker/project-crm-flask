"""Finance > Journal Entries.

Moves money between the Expense module's accounts (ExpenseAccount — the ones
created from Expenses > Manage Accounts). A journal entry is a voucher header
(FinanceJournalEntry: number, date, reference, recurring, description) plus two
or more debit/credit lines that must balance. Each line is posted as an
ExpenseAccountTransaction with transaction_type='journal', so every account's
balance, ledger and Account Activity reflect journal entries automatically.

Debit = money IN to an account, Credit = money OUT (same convention as
ExpenseAccount.balance). Lines only count towards balances once the entry is
approved: admins' entries are approved on save, other users' wait for an
admin to approve them.
"""
from datetime import datetime
from html.parser import HTMLParser
from html import escape

from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, or_

from app import db
from app.models import ExpenseAccount, ExpenseAccountTransaction, FinanceJournalEntry, Vendor, Customer
from app.utils import log_activity

bp = Blueprint('finance_journal', __name__)

RECURRING_UNITS = ('day', 'week', 'month', 'year')
RECURRING_PRESETS = list(range(1, 13))  # "Every N month(s)" quick options


# ─── Permissions ───────────────────────────────────────────────────────────

def _is_admin():
    return bool(getattr(current_user, 'is_admin', False))


def _can(action):
    if _is_admin():
        return True
    if action == 'view':
        return bool(getattr(current_user, 'can_view_accounting', False)
                    or getattr(current_user, 'can_view_expenses', False))
    return bool(getattr(current_user, f'can_{action}_accounting', False))


def _deny(action):
    flash(f'You do not have permission to {action} journal entries.', 'danger')
    return redirect(url_for('finance_journal.index') if _can('view') else url_for('dashboard.index'))


# ─── Rich-text sanitising (TinyMCE description) ───────────────────────────

_ALLOWED_TAGS = {'p', 'br', 'b', 'strong', 'i', 'em', 'u', 's', 'span', 'div', 'ul', 'ol', 'li',
                 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'a', 'table', 'thead', 'tbody',
                 'tr', 'th', 'td', 'hr', 'sub', 'sup', 'pre', 'code'}
_ALLOWED_ATTRS = {'style', 'href', 'title', 'colspan', 'rowspan', 'target'}
_VOID_TAGS = {'br', 'hr'}


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._skip = 0  # inside <script>/<style>

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._skip += 1
            return
        if self._skip or tag not in _ALLOWED_TAGS:
            return
        kept = []
        for name, value in attrs:
            value = value or ''
            if name not in _ALLOWED_ATTRS:
                continue
            low = value.strip().lower()
            if name == 'href' and not low.startswith(('http://', 'https://', 'mailto:', '/', '#')):
                continue
            if name == 'style' and ('expression' in low or 'url(' in low or 'javascript' in low):
                continue
            kept.append(f' {name}="{escape(value, quote=True)}"')
        self.out.append(f'<{tag}{"".join(kept)}>')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip or tag not in _ALLOWED_TAGS or tag in _VOID_TAGS:
            return
        self.out.append(f'</{tag}>')

    def handle_data(self, data):
        if not self._skip:
            self.out.append(escape(data, quote=False))


def _sanitize_html(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    s = _Sanitizer()
    s.feed(raw)
    s.close()
    cleaned = ''.join(s.out).strip()
    # TinyMCE posts an "empty" editor as <p></p> / <p>&nbsp;</p>
    text_only = cleaned.replace('<p>', '').replace('</p>', '').replace('\xa0', '').replace('<br>', '').strip()
    return cleaned if text_only else None


# ─── Helpers ───────────────────────────────────────────────────────────────

def _next_number():
    return (db.session.query(func.max(FinanceJournalEntry.number)).scalar() or 0) + 1


def _parse_date(raw):
    raw = (raw or '').strip()
    for fmt in ('%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _to_amount(raw):
    try:
        return round(float(str(raw or '').replace(',', '').strip() or 0), 2)
    except ValueError:
        return None


def _add_interval(d, n, unit):
    return d + relativedelta(**{f'{unit}s': n})


def _accounts_for_form(entry=None):
    """Active accounts, plus any inactive one already used on this entry so
    editing an old entry never silently drops a line."""
    accounts = ExpenseAccount.query.filter_by(is_active=True).order_by(ExpenseAccount.name).all()
    if entry:
        have = {a.id for a in accounts}
        for l in entry.lines:
            if l.account and l.account_id not in have:
                accounts.append(l.account)
                have.add(l.account_id)
    return accounts


def _read_form(entry=None):
    """Parses and validates the posted form. Returns (data, lines, errors);
    `lines` is also used to re-render the form on error."""
    errors = []
    data = {
        'number': (request.form.get('number') or '').strip(),
        'date': (request.form.get('date') or '').strip(),
        'reference': (request.form.get('reference') or '').strip(),
        'description': request.form.get('description') or '',
        'recurring': (request.form.get('recurring') or 'no').strip(),
        'custom_interval': (request.form.get('custom_interval') or '').strip(),
        'custom_unit': (request.form.get('custom_unit') or 'month').strip(),
        'cycles': (request.form.get('cycles') or '0').strip(),
    }

    # Number
    try:
        number = int(data['number'])
        if number <= 0:
            raise ValueError
    except ValueError:
        number = None
        errors.append('Number must be a positive whole number.')
    if number:
        clash = FinanceJournalEntry.query.filter(FinanceJournalEntry.number == number)
        if entry:
            clash = clash.filter(FinanceJournalEntry.id != entry.id)
        if clash.first():
            errors.append(f'Journal number {number} is already used — the next free number is {_next_number()}.')
    data['number_int'] = number

    # Date
    data['date_obj'] = _parse_date(data['date'])
    if not data['date_obj']:
        errors.append('Enter a valid journal date.')

    # Recurring
    data['is_recurring'] = False
    data['interval'] = data['unit'] = None
    if data['recurring'] == 'custom':
        try:
            n = int(data['custom_interval'])
            if n <= 0:
                raise ValueError
        except ValueError:
            n = None
            errors.append('Custom recurring: "Repeat every" must be a positive number.')
        if data['custom_unit'] not in RECURRING_UNITS:
            errors.append('Custom recurring: choose day(s), week(s), month(s) or year(s).')
        data.update(is_recurring=True, interval=n, unit=data['custom_unit'])
    elif data['recurring'] != 'no':
        try:
            n = int(data['recurring'])
            if n not in RECURRING_PRESETS:
                raise ValueError
            data.update(is_recurring=True, interval=n, unit='month')
        except ValueError:
            errors.append('Choose a valid recurring option.')
    try:
        data['cycles_int'] = max(0, int(data['cycles'] or 0))
    except ValueError:
        data['cycles_int'] = 0
        errors.append('Total cycles must be a whole number (0 = unlimited).')

    # Lines
    acc_ids = request.form.getlist('line_account_id[]')
    debits = request.form.getlist('line_debit[]')
    credits = request.form.getlist('line_credit[]')
    descs = request.form.getlist('line_description[]')
    parties = request.form.getlist('line_party[]')
    allowed = {a.id: a for a in _accounts_for_form(entry)}

    lines = []
    for i in range(max(len(acc_ids), len(debits), len(credits), len(descs))):
        raw_acc = (acc_ids[i] if i < len(acc_ids) else '') or ''
        raw_dr = (debits[i] if i < len(debits) else '') or ''
        raw_cr = (credits[i] if i < len(credits) else '') or ''
        desc = ((descs[i] if i < len(descs) else '') or '').strip()
        party = ((parties[i] if i < len(parties) else '') or '').strip()
        line = {'account_id': int(raw_acc) if raw_acc.isdigit() else None,
                'debit': raw_dr.strip(), 'credit': raw_cr.strip(), 'description': desc,
                'party': party, 'vendor_id': None, 'customer_id': None}
        kind, _, pid = party.partition(':')
        if pid.isdigit():
            if kind == 'v':
                line['vendor_id'] = int(pid)
            elif kind == 'c':
                line['customer_id'] = int(pid)
        if not line['account_id'] and not line['debit'] and not line['credit'] and not desc:
            continue  # completely blank row
        lines.append(line)

        row = len(lines)
        dr, cr = _to_amount(raw_dr), _to_amount(raw_cr)
        if dr is None or cr is None or dr < 0 or cr < 0:
            errors.append(f'Row {row}: amounts must be positive numbers.')
            continue
        if line['vendor_id'] and not Vendor.query.get(line['vendor_id']):
            errors.append(f'Row {row}: the selected vendor no longer exists.')
        if line['customer_id'] and not Customer.query.get(line['customer_id']):
            errors.append(f'Row {row}: the selected customer no longer exists.')
        if not line['account_id']:
            errors.append(f'Row {row}: select an account.')
        elif line['account_id'] not in allowed:
            errors.append(f'Row {row}: the selected account is inactive or no longer exists.')
        if dr and cr:
            errors.append(f'Row {row}: enter either a debit or a credit, not both.')
        elif not dr and not cr:
            errors.append(f'Row {row}: enter a debit or a credit amount.')
        line['entry_type'] = 'debit' if dr else 'credit'
        line['amount'] = dr or cr

    valid = [l for l in lines if l.get('amount')]
    total_dr = round(sum(l['amount'] for l in valid if l['entry_type'] == 'debit'), 2)
    total_cr = round(sum(l['amount'] for l in valid if l['entry_type'] == 'credit'), 2)
    if len(lines) < 2:
        errors.append('A journal entry needs at least two lines — one account debited and one credited.')
    elif not errors:
        if not total_dr or not total_cr:
            errors.append('A journal entry needs at least one debit line and one credit line.')
        elif abs(total_dr - total_cr) >= 0.005:
            errors.append(f'Debits ({total_dr:,.2f}) and credits ({total_cr:,.2f}) must be equal — '
                          f'difference is {abs(total_dr - total_cr):,.2f}.')
    return data, lines, errors


def _post_lines(entry, lines):
    """(Re)creates the entry's ExpenseAccountTransaction lines."""
    for old in list(entry.lines):
        entry.lines.remove(old)
    db.session.flush()

    approved = entry.status == 'approved'
    names = {a.id: a.name for a in ExpenseAccount.query.filter(
        ExpenseAccount.id.in_({l['account_id'] for l in lines})).all()}

    for l in lines:
        opposite = [o['account_id'] for o in lines if o['entry_type'] != l['entry_type']]
        opposite_unique = list(dict.fromkeys(opposite))
        entry.lines.append(ExpenseAccountTransaction(
            account_id=l['account_id'],
            date=entry.date,
            entry_type=l['entry_type'],
            amount=l['amount'],
            description=l['description'] or None,
            reference=entry.reference,
            vendor_id=l.get('vendor_id'),
            customer_id=l.get('customer_id'),
            transaction_type='journal',
            counterparty_account_id=opposite_unique[0] if len(opposite_unique) == 1 else None,
            payee=(', '.join(names.get(i, '') for i in opposite_unique))[:160] or None,
            is_approved=approved,
            is_rejected=entry.status == 'rejected',
            rejection_reason=entry.rejection_reason if entry.status == 'rejected' else None,
            approved_by=entry.approved_by if approved else None,
            approved_at=entry.approved_at if approved else None,
            created_by=entry.created_by,
        ))


def _sync_line_status(entry):
    for l in entry.lines:
        l.is_approved = entry.status == 'approved'
        l.is_rejected = entry.status == 'rejected'
        l.rejection_reason = entry.rejection_reason if entry.status == 'rejected' else None
        l.approved_by = entry.approved_by if entry.status == 'approved' else None
        l.approved_at = entry.approved_at if entry.status == 'approved' else None


def _lines_from_entry(entry):
    return [{'account_id': l.account_id,
             'debit': f'{l.amount:.2f}' if l.entry_type == 'debit' else '',
             'credit': f'{l.amount:.2f}' if l.entry_type == 'credit' else '',
             'description': l.description or '',
             'party': f'v:{l.vendor_id}' if l.vendor_id else (f'c:{l.customer_id}' if l.customer_id else '')}
            for l in entry.lines]


def _form_from_entry(entry):
    if entry.is_recurring and entry.recurring_unit == 'month' and entry.recurring_interval in RECURRING_PRESETS:
        recurring = str(entry.recurring_interval)
    elif entry.is_recurring:
        recurring = 'custom'
    else:
        recurring = 'no'
    return {'number': entry.number, 'date': entry.date.strftime('%Y-%m-%d'),
            'reference': entry.reference or '', 'description': entry.description or '',
            'recurring': recurring, 'custom_interval': entry.recurring_interval or 1,
            'custom_unit': entry.recurring_unit or 'month', 'cycles': entry.recurring_cycles or 0}


def _render_form(entry, form, lines, errors=None):
    return render_template('finance_journal/form.html', entry=entry, form=form,
                           lines=lines or [{}, {}], accounts=_accounts_for_form(entry),
                           presets=RECURRING_PRESETS, units=RECURRING_UNITS,
                           vendors=Vendor.query.order_by(Vendor.name).all(),
                           customers=Customer.query.order_by(Customer.name).all(),
                           errors=errors or [])


def generate_due_recurring():
    """Creates every recurring copy that has fallen due (up to today) from
    approved recurring entries. Safe to call repeatedly — each template
    tracks last_recurring_date / recurring_cycles_done."""
    today = datetime.utcnow().date()
    created = 0
    templates = FinanceJournalEntry.query.filter(
        FinanceJournalEntry.is_recurring.is_(True),
        FinanceJournalEntry.status == 'approved',
        FinanceJournalEntry.recurring_parent_id.is_(None),
    ).all()
    for t in templates:
        if not t.recurring_interval or t.recurring_unit not in RECURRING_UNITS or len(t.lines) < 2:
            continue
        guard = 0
        while guard < 120:
            guard += 1
            if t.recurring_cycles and (t.recurring_cycles_done or 0) >= t.recurring_cycles:
                break
            next_date = _add_interval(t.last_recurring_date or t.date, t.recurring_interval, t.recurring_unit)
            if next_date > today:
                break
            copy = FinanceJournalEntry(
                number=_next_number(), date=next_date, reference=t.reference, description=t.description,
                status='approved', approved_by=t.approved_by, approved_at=datetime.utcnow(),
                recurring_parent_id=t.id, created_by=t.created_by,
            )
            db.session.add(copy)
            db.session.flush()
            _post_lines(copy, [{'account_id': l.account_id, 'entry_type': l.entry_type,
                                'amount': l.amount, 'description': l.description,
                                'vendor_id': l.vendor_id, 'customer_id': l.customer_id} for l in t.lines])
            t.last_recurring_date = next_date
            t.recurring_cycles_done = (t.recurring_cycles_done or 0) + 1
            created += 1
    if created:
        db.session.commit()
    return created


# ─── Routes ────────────────────────────────────────────────────────────────

@bp.route('/')
@login_required
def index():
    if not _can('view'):
        return _deny('view')

    try:
        generated = generate_due_recurring()
        if generated:
            flash(f'{generated} recurring journal entr{"y" if generated == 1 else "ies"} generated.', 'info')
    except Exception as e:  # never block the list on a recurring hiccup
        db.session.rollback()
        flash(f'Could not generate recurring entries: {e}', 'warning')

    date_from = _parse_date(request.args.get('date_from'))
    date_to = _parse_date(request.args.get('date_to'))
    status = (request.args.get('status') or '').strip()
    account_id = request.args.get('account_id', type=int)
    q = (request.args.get('q') or '').strip()

    query = FinanceJournalEntry.query
    if date_from:
        query = query.filter(FinanceJournalEntry.date >= date_from)
    if date_to:
        query = query.filter(FinanceJournalEntry.date <= date_to)
    if status in ('pending', 'approved', 'rejected'):
        query = query.filter(FinanceJournalEntry.status == status)
    elif status == 'recurring':
        query = query.filter(FinanceJournalEntry.is_recurring.is_(True))
    if account_id:
        query = query.filter(FinanceJournalEntry.lines.any(ExpenseAccountTransaction.account_id == account_id))
    if q:
        like = f'%{q}%'
        conds = [FinanceJournalEntry.reference.ilike(like), FinanceJournalEntry.description.ilike(like),
                 FinanceJournalEntry.lines.any(ExpenseAccountTransaction.description.ilike(like)),
                 FinanceJournalEntry.lines.any(ExpenseAccountTransaction.account.has(ExpenseAccount.name.ilike(like))),
                 FinanceJournalEntry.lines.any(ExpenseAccountTransaction.vendor.has(Vendor.name.ilike(like))),
                 FinanceJournalEntry.lines.any(ExpenseAccountTransaction.customer.has(Customer.name.ilike(like)))]
        digits = q.upper().replace('JV-', '').strip()
        if digits.isdigit():
            conds.append(FinanceJournalEntry.number == int(digits))
        query = query.filter(or_(*conds))

    entries = query.order_by(FinanceJournalEntry.date.desc(), FinanceJournalEntry.number.desc()).all()

    counts = dict(db.session.query(FinanceJournalEntry.status, func.count(FinanceJournalEntry.id))
                  .group_by(FinanceJournalEntry.status).all())
    total_amount = sum(e.total_debit for e in entries if e.status == 'approved')

    return render_template('finance_journal/index.html', entries=entries, counts=counts,
                           total_amount=total_amount,
                           accounts=ExpenseAccount.query.order_by(ExpenseAccount.name).all(),
                           f={'date_from': request.args.get('date_from', ''),
                              'date_to': request.args.get('date_to', ''),
                              'status': status, 'account_id': account_id, 'q': q})


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not _can('add'):
        return _deny('create')

    if request.method == 'GET':
        src = FinanceJournalEntry.query.get(request.args.get('copy', type=int)) if request.args.get('copy') else None
        form = {'number': _next_number(), 'date': datetime.utcnow().strftime('%Y-%m-%d'), 'reference': '',
                'description': '', 'recurring': 'no', 'custom_interval': 1, 'custom_unit': 'month', 'cycles': 0}
        lines = None
        if src:
            form.update(reference=src.reference or '', description=src.description or '')
            lines = _lines_from_entry(src)
        return _render_form(None, form, lines)

    data, lines, errors = _read_form()
    if errors:
        return _render_form(None, data, lines, errors)

    now = datetime.utcnow()
    entry = FinanceJournalEntry(
        number=data['number_int'], date=data['date_obj'], reference=data['reference'] or None,
        description=_sanitize_html(data['description']),
        is_recurring=data['is_recurring'], recurring_interval=data['interval'], recurring_unit=data['unit'],
        recurring_cycles=data['cycles_int'] if data['is_recurring'] else 0, recurring_cycles_done=0,
        status='approved' if _is_admin() else 'pending',
        approved_by=current_user.id if _is_admin() else None, approved_at=now if _is_admin() else None,
        created_by=current_user.id,
    )
    db.session.add(entry)
    db.session.flush()
    _post_lines(entry, lines)
    db.session.commit()

    log_activity('Finance', f'Created journal entry {entry.code}',
                 f'Amount: {entry.total_debit:,.2f}; status: {entry.status}')
    if entry.status == 'approved':
        flash(f'Journal entry {entry.code} saved and posted to the accounts.', 'success')
    else:
        flash(f'Journal entry {entry.code} saved — it will hit the account balances once an admin approves it.', 'info')
    if request.form.get('save_and_new'):
        return redirect(url_for('finance_journal.create'))
    return redirect(url_for('finance_journal.view', id=entry.id))


@bp.route('/<int:id>')
@login_required
def view(id):
    if not _can('view'):
        return _deny('view')
    entry = FinanceJournalEntry.query.get_or_404(id)
    next_run = None
    if entry.is_recurring and entry.status == 'approved' and entry.recurring_interval and entry.recurring_unit:
        if not entry.recurring_cycles or (entry.recurring_cycles_done or 0) < entry.recurring_cycles:
            next_run = _add_interval(entry.last_recurring_date or entry.date,
                                     entry.recurring_interval, entry.recurring_unit)
    return render_template('finance_journal/view.html', entry=entry, next_run=next_run)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    entry = FinanceJournalEntry.query.get_or_404(id)
    if not _can('edit'):
        return _deny('edit')
    if entry.status == 'approved' and not _is_admin():
        flash('This entry is already approved — only an admin can change it.', 'warning')
        return redirect(url_for('finance_journal.view', id=id))

    if request.method == 'GET':
        return _render_form(entry, _form_from_entry(entry), _lines_from_entry(entry))

    data, lines, errors = _read_form(entry)
    if errors:
        return _render_form(entry, data, lines, errors)

    entry.number = data['number_int']
    entry.date = data['date_obj']
    entry.reference = data['reference'] or None
    entry.description = _sanitize_html(data['description'])
    was_recurring = entry.is_recurring
    entry.is_recurring = data['is_recurring']
    entry.recurring_interval = data['interval']
    entry.recurring_unit = data['unit']
    entry.recurring_cycles = data['cycles_int'] if data['is_recurring'] else 0
    if data['is_recurring'] and not was_recurring:
        entry.recurring_cycles_done = 0
        entry.last_recurring_date = None
    if not _is_admin():
        # Any change by a non-admin goes back for review.
        entry.status = 'pending'
        entry.rejection_reason = None
        entry.approved_by = entry.approved_at = None
    _post_lines(entry, lines)
    db.session.commit()

    log_activity('Finance', f'Edited journal entry {entry.code}', f'Amount: {entry.total_debit:,.2f}')
    flash(f'Journal entry {entry.code} updated.', 'success')
    return redirect(url_for('finance_journal.view', id=entry.id))


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    entry = FinanceJournalEntry.query.get_or_404(id)
    if not _can('delete'):
        return _deny('delete')
    if entry.status == 'approved' and not _is_admin():
        flash('Only an admin can delete an approved journal entry.', 'warning')
        return redirect(url_for('finance_journal.view', id=id))
    code, amount = entry.code, entry.total_debit

    # Optionally take the recurring copies this entry generated with it.
    to_delete = [entry]
    if request.form.get('delete_children'):
        to_delete += list(entry.recurring_children)
    else:
        for child in entry.recurring_children:
            child.recurring_parent_id = None  # generated copies stay; they're real postings

    # Net effect each account is losing (only approved lines ever counted).
    reversed_by_acct = {}
    for e in to_delete:
        if e.status != 'approved':
            continue
        for l in e.lines:
            delta = (l.amount or 0) if l.entry_type == 'debit' else -(l.amount or 0)
            name = l.account.name if l.account else f'#{l.account_id}'
            reversed_by_acct[name] = reversed_by_acct.get(name, 0) + delta

    # A deleted generated copy frees up one cycle on its template.
    parent = entry.recurring_parent
    if parent and parent not in to_delete and (parent.recurring_cycles_done or 0) > 0:
        parent.recurring_cycles_done -= 1

    ids = [e.id for e in to_delete]
    db.session.flush()  # detached children / parent cycle count first
    # Remove every posted line explicitly (not just the ones loaded on the
    # relationship), so no orphan row can keep moving an account balance.
    ExpenseAccountTransaction.query.filter(
        ExpenseAccountTransaction.journal_entry_id.in_(ids)).delete(synchronize_session=False)
    FinanceJournalEntry.query.filter(FinanceJournalEntry.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()

    summary = ', '.join(f'{n} {"−" if d > 0 else "+"}{abs(d):,.2f}' for n, d in reversed_by_acct.items() if abs(d) >= 0.005)
    extra = f' and {len(to_delete) - 1} recurring cop{"y" if len(to_delete) == 2 else "ies"}' if len(to_delete) > 1 else ''
    log_activity('Finance', f'Deleted journal entry {code}{extra}', f'Amount: {amount:,.2f}; reversed: {summary or "nothing posted"}')
    if summary:
        flash(f'Journal entry {code}{extra} deleted. Balances reversed: {summary}.', 'success')
    else:
        flash(f'Journal entry {code}{extra} deleted (it was not posted, so no balance changed).', 'success')
    return redirect(url_for('finance_journal.index'))


@bp.route('/<int:id>/approve', methods=['POST'])
@login_required
def approve(id):
    if not _is_admin():
        return _deny('approve')
    entry = FinanceJournalEntry.query.get_or_404(id)
    entry.status = 'approved'
    entry.rejection_reason = None
    entry.approved_by = current_user.id
    entry.approved_at = datetime.utcnow()
    _sync_line_status(entry)
    db.session.commit()
    log_activity('Finance', f'Approved journal entry {entry.code}', f'Amount: {entry.total_debit:,.2f}')
    flash(f'{entry.code} approved and posted to the accounts.', 'success')
    return redirect(request.referrer or url_for('finance_journal.view', id=id))


@bp.route('/<int:id>/reject', methods=['POST'])
@login_required
def reject(id):
    if not _is_admin():
        return _deny('reject')
    entry = FinanceJournalEntry.query.get_or_404(id)
    entry.status = 'rejected'
    entry.rejection_reason = (request.form.get('reason') or '').strip() or None
    entry.approved_by = entry.approved_at = None
    _sync_line_status(entry)
    db.session.commit()
    log_activity('Finance', f'Rejected journal entry {entry.code}', entry.rejection_reason or '')
    flash(f'{entry.code} rejected — it no longer affects the account balances.', 'warning')
    return redirect(request.referrer or url_for('finance_journal.view', id=id))
