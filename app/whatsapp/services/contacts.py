"""Contacts: find-or-create by normalized number, consent, duplicates,
merging and CSV import/export."""
import csv
import io
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.whatsapp.models import (WhatsAppCampaignRecipient, WhatsAppContact, WhatsAppConversation,
                                 WhatsAppMessage, WhatsAppNote)
from app.whatsapp.services import phone as phone_svc

CSV_FIELDS = ['name', 'phone', 'email', 'tags', 'consent_status', 'consent_source', 'notes']
EXPORT_FIELDS = ['name', 'phone', 'email', 'tags', 'consent_status', 'consent_source', 'consent_at',
                 'opted_out_at', 'last_message_at', 'linked_customer', 'assigned_to', 'created_at']
MAX_IMPORT_ROWS = 5000


class ContactError(ValueError):
    pass


def find_by_wa_id(wa_id):
    return WhatsAppContact.query.filter_by(wa_id=wa_id).first()


def get_or_create(wa_id, profile_name=None, **fields):
    """Race-safe: two webhook deliveries for a new number can't create two rows."""
    contact = find_by_wa_id(wa_id)
    if contact is None:
        contact = WhatsAppContact(wa_id=wa_id, profile_name=(profile_name or None) and profile_name[:150], **fields)
        try:
            with db.session.begin_nested():
                db.session.add(contact)
        except IntegrityError:
            contact = find_by_wa_id(wa_id)
    elif profile_name and contact.profile_name != profile_name[:150]:
        contact.profile_name = profile_name[:150]
    return contact


def get_or_create_conversation(contact):
    conv = WhatsAppConversation.query.filter_by(contact_id=contact.id).first()
    if conv is None:
        conv = WhatsAppConversation(contact_id=contact.id, assigned_to_id=contact.assigned_to_id)
        try:
            with db.session.begin_nested():
                db.session.add(conv)
        except IntegrityError:
            conv = WhatsAppConversation.query.filter_by(contact_id=contact.id).first()
    return conv


def set_consent(contact, status, source=None):
    if status not in WhatsAppContact.CONSENT:
        raise ContactError('Unknown consent status.')
    now = datetime.utcnow()
    if status == 'opted_in' and contact.consent_status != 'opted_in':
        contact.consent_at = now
        contact.opted_out_at = None
    elif status == 'opted_out' and contact.consent_status != 'opted_out':
        contact.opted_out_at = now
    contact.consent_status = status
    if source is not None:
        contact.consent_source = (source or '')[:120] or None
    contact.updated_at = now


def apply_form(contact, form, default_cc, is_new):
    """Validate and copy contact fields from a request form. Returns errors list."""
    errors = []
    name = (form.get('name') or '').strip()[:150]
    raw_phone = form.get('phone') or ''
    if is_new or raw_phone:
        try:
            wa_id = phone_svc.normalize(raw_phone, default_cc)
        except phone_svc.InvalidPhone as e:
            errors.append(str(e))
        else:
            other = find_by_wa_id(wa_id)
            if other and other.id != contact.id:
                errors.append(f'A contact with +{wa_id} already exists ({other.display_name}).')
            else:
                contact.wa_id = wa_id
    email = (form.get('email') or '').strip()[:120]
    if email and '@' not in email:
        errors.append('Email address is not valid.')
    if errors:
        return errors
    contact.name = name or None
    contact.email = email or None
    contact.notes = (form.get('notes') or '').strip()[:5000] or None
    contact.set_tags((form.get('tags') or '').split(','))
    cust = form.get('customer_id')
    contact.customer_id = int(cust) if cust and str(cust).isdigit() else None
    assigned = form.get('assigned_to_id')
    contact.assigned_to_id = int(assigned) if assigned and str(assigned).isdigit() else None
    consent = form.get('consent_status')
    if consent and consent != contact.consent_status:
        set_consent(contact, consent, form.get('consent_source') or 'Manual (CRM)')
    elif form.get('consent_source') is not None:
        contact.consent_source = (form.get('consent_source') or '').strip()[:120] or None
    contact.updated_at = datetime.utcnow()
    return []


def search(q=None, tag=None, consent=None):
    query = WhatsAppContact.query
    if q:
        like = f'%{q.strip()}%'
        digits = ''.join(ch for ch in q if ch.isdigit())
        conds = [WhatsAppContact.name.ilike(like), WhatsAppContact.profile_name.ilike(like),
                 WhatsAppContact.email.ilike(like)]
        if digits:
            conds.append(WhatsAppContact.wa_id.like(f'%{digits.lstrip("0")}%'))
        query = query.filter(or_(*conds))
    if tag:
        query = query.filter(WhatsAppContact.tags.like(f'%,{tag.strip().lower()},%'))
    if consent in WhatsAppContact.CONSENT:
        query = query.filter(WhatsAppContact.consent_status == consent)
    return query


def all_tags():
    tags = set()
    for (t,) in db.session.query(WhatsAppContact.tags).filter(WhatsAppContact.tags != '').distinct():
        tags.update(x for x in t.split(',') if x)
    return sorted(tags)


def find_duplicates(limit=100):
    """Groups of contacts that look like the same person: same linked CRM
    customer, same email, or same last 9 digits of the number (e.g. one saved
    with the wrong country code). Returns list of lists of contacts."""
    groups, seen = [], set()

    def add(ids):
        key = tuple(sorted(ids))
        if len(key) > 1 and key not in seen:
            seen.add(key)
            groups.append(WhatsAppContact.query.filter(WhatsAppContact.id.in_(key))
                          .order_by(WhatsAppContact.created_at).all())

    for col in (WhatsAppContact.customer_id, func.lower(WhatsAppContact.email),
                func.substr(WhatsAppContact.wa_id, -9)):
        rows = (db.session.query(col, func.group_concat(WhatsAppContact.id))
                .filter(col.isnot(None)).group_by(col).having(func.count(WhatsAppContact.id) > 1)
                .limit(limit).all())
        for _, ids in rows:
            add(int(i) for i in str(ids).split(','))
    return groups[:limit]


def merge(primary, other):
    """Move everything from ``other`` into ``primary`` then delete ``other``.
    Caller commits and audits. Messages keep their Meta ids."""
    if primary.id == other.id:
        raise ContactError('Choose two different contacts.')
    conv_p = get_or_create_conversation(primary)
    conv_o = WhatsAppConversation.query.filter_by(contact_id=other.id).first()
    if conv_o:
        WhatsAppMessage.query.filter_by(conversation_id=conv_o.id).update(
            {'conversation_id': conv_p.id}, synchronize_session=False)
        conv_p.unread_count = (conv_p.unread_count or 0) + (conv_o.unread_count or 0)
        for attr in ('last_message_at', 'last_inbound_at'):
            if getattr(conv_o, attr) and (not getattr(conv_p, attr) or getattr(conv_o, attr) > getattr(conv_p, attr)):
                setattr(conv_p, attr, getattr(conv_o, attr))
                if attr == 'last_message_at':
                    conv_p.last_message_preview = conv_o.last_message_preview
                    conv_p.last_message_direction = conv_o.last_message_direction
        db.session.delete(conv_o)
    WhatsAppNote.query.filter_by(contact_id=other.id).update({'contact_id': primary.id}, synchronize_session=False)
    # Campaign rows: keep the primary's row where both were in the same campaign.
    for r in WhatsAppCampaignRecipient.query.filter_by(contact_id=other.id).all():
        if WhatsAppCampaignRecipient.query.filter_by(campaign_id=r.campaign_id, contact_id=primary.id).first():
            db.session.delete(r)
        else:
            r.contact_id = primary.id
    primary.set_tags(primary.tag_list + other.tag_list)
    for attr in ('name', 'email', 'customer_id', 'assigned_to_id', 'profile_name'):
        if not getattr(primary, attr) and getattr(other, attr):
            setattr(primary, attr, getattr(other, attr))
    # An opt-out on either record wins.
    if other.consent_status == 'opted_out' and primary.consent_status != 'opted_out':
        set_consent(primary, 'opted_out', 'Merged contact had opted out')
    elif primary.consent_status == 'unknown' and other.consent_status == 'opted_in':
        primary.consent_status, primary.consent_at = 'opted_in', other.consent_at
        primary.consent_source = other.consent_source
    if other.notes:
        primary.notes = ((primary.notes + '\n\n') if primary.notes else '') + other.notes
    primary.updated_at = datetime.utcnow()
    db.session.flush()
    db.session.delete(other)


# ── CSV ───────────────────────────────────────────────────────────────────

def parse_import(file_bytes, default_cc):
    """Parse a CSV upload into preview rows. Nothing is saved here.
    Each row: {line, name, wa_id, email, tags, consent_status, consent_source, notes, action, error}."""
    try:
        text = file_bytes.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = file_bytes.decode('latin-1')
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ContactError('The file is empty.')
    headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    phone_col = headers.get('phone') or headers.get('whatsapp') or headers.get('mobile') or headers.get('number')
    if not phone_col:
        raise ContactError('The CSV needs a "phone" column. Expected columns: ' + ', '.join(CSV_FIELDS))
    rows, seen = [], set()
    for i, raw in enumerate(reader, start=2):
        if len(rows) >= MAX_IMPORT_ROWS:
            raise ContactError(f'Import at most {MAX_IMPORT_ROWS} rows at a time.')

        def col(name):
            key = headers.get(name)
            return (raw.get(key) or '').strip() if key else ''

        row = {'line': i, 'name': col('name')[:150], 'email': col('email')[:120], 'tags': col('tags'),
               'consent_status': (col('consent_status') or 'unknown').lower(),
               'consent_source': col('consent_source')[:120], 'notes': col('notes')[:2000],
               'raw_phone': (raw.get(phone_col) or '').strip(), 'wa_id': None, 'action': 'create', 'error': None}
        try:
            row['wa_id'] = phone_svc.normalize(row['raw_phone'], default_cc)
        except phone_svc.InvalidPhone as e:
            row['error'], row['action'] = str(e), 'skip'
        if row['consent_status'] not in WhatsAppContact.CONSENT:
            row['error'], row['action'] = 'consent_status must be unknown, opted_in or opted_out', 'skip'
        if row['consent_status'] == 'opted_in' and not row['consent_source']:
            row['error'], row['action'] = 'opted_in rows need a consent_source (where consent was given)', 'skip'
        if row['action'] != 'skip':
            if row['wa_id'] in seen:
                row['error'], row['action'] = 'Duplicate of an earlier row in this file', 'skip'
            elif find_by_wa_id(row['wa_id']):
                row['action'] = 'update'
            seen.add(row['wa_id'])
        rows.append(row)
    return rows


def apply_import(rows, user_id):
    """Create/update contacts from validated preview rows. An existing
    contact's opt-out is never overwritten by an import."""
    created = updated = 0
    for row in rows:
        if row.get('action') not in ('create', 'update') or not row.get('wa_id'):
            continue
        contact = find_by_wa_id(row['wa_id'])
        if contact is None:
            contact = WhatsAppContact(wa_id=row['wa_id'])
            db.session.add(contact)
            created += 1
        else:
            updated += 1
        if row['name']:
            contact.name = row['name']
        if row['email']:
            contact.email = row['email']
        if row['notes']:
            contact.notes = row['notes']
        if row['tags']:
            contact.set_tags(contact.tag_list + row['tags'].replace(';', ',').split(','))
        if row['consent_status'] != 'unknown' and contact.consent_status != 'opted_out':
            set_consent(contact, row['consent_status'], (row['consent_source'] or 'CSV import')[:120])
        contact.updated_at = datetime.utcnow()
    return created, updated


def export_csv(query):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(EXPORT_FIELDS)
    for c in query.yield_per(500):
        w.writerow([_csv_safe(v) for v in (
            c.name or c.profile_name or '', '+' + c.wa_id, c.email or '', ','.join(c.tag_list), c.consent_status,
            c.consent_source or '', _iso(c.consent_at), _iso(c.opted_out_at), _iso(c.last_message_at),
            c.customer.name if c.customer else '', c.assigned_to.username if c.assigned_to else '',
            _iso(c.created_at))])
    return out.getvalue()


def _iso(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else ''


def _csv_safe(value):
    """Stop spreadsheet formula injection from names typed by customers."""
    value = '' if value is None else str(value)
    return "'" + value if value[:1] in ('=', '+', '-', '@') and not value[1:2].isdigit() else value
