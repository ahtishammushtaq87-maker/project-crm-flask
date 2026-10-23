"""Processing of verified webhook POSTs from Meta.

Payload shape (Graph API v18+; checked against the Cloud API webhook reference):

  {"object": "whatsapp_business_account",
   "entry": [{"id": "<WABA id>", "changes": [{"field": "messages", "value": {
       "messaging_product": "whatsapp",
       "metadata": {"display_phone_number": "...", "phone_number_id": "..."},
       "contacts": [{"profile": {"name": "..."}, "wa_id": "..."}],
       "messages": [{"from": "...", "id": "wamid...", "timestamp": "1700000000", "type": "text",
                     "text": {"body": "..."}, "context": {"id": "wamid..."}}],
       "statuses": [{"id": "wamid...", "status": "delivered", "timestamp": "...", "recipient_id": "...",
                     "errors": [{"code": 131047, "title": "...", "error_data": {"details": "..."}}]}],
       "errors": [...]}}]}]}

and field "message_template_status_update" for template review results.

Idempotency: the whole body is deduplicated by its SHA-256 (Meta retries send
the same body), messages by their wamid (unique column), and status events by
(wamid, status, timestamp) (unique constraint). Processing only touches the
database, so the HTTP response goes back to Meta quickly.
"""
import hashlib
import json
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app import db
from app.whatsapp.models import (WhatsAppCampaignRecipient, WhatsAppMessage, WhatsAppStatusEvent,
                                 WhatsAppWebhookEvent)
from app.whatsapp.services import contacts as contact_svc
from app.whatsapp.services import core, messaging
from app.whatsapp.services import templates as tpl_svc

MEDIA_TYPES = ('image', 'video', 'audio', 'document', 'sticker')


def _ts(value):
    try:
        return datetime.utcfromtimestamp(int(value))
    except (TypeError, ValueError, OverflowError, OSError):
        return datetime.utcnow()


def _clip(v, n):
    return str(v)[:n] if v not in (None, '') else None


def register_event(raw_body, signature_ok):
    """Insert the dedupe row. Returns (event, is_duplicate)."""
    key = hashlib.sha256(raw_body).hexdigest()
    existing = WhatsAppWebhookEvent.query.filter_by(dedupe_key=key).first()
    if existing:
        return existing, True
    ev = WhatsAppWebhookEvent(dedupe_key=key, signature_ok=signature_ok)
    try:
        with db.session.begin_nested():
            db.session.add(ev)
    except IntegrityError:   # a concurrent delivery of the same body won the race
        return WhatsAppWebhookEvent.query.filter_by(dedupe_key=key).first(), True
    return ev, False


def process(payload, event, settings):
    """Apply a parsed payload. Returns a list of automation events
    [(trigger, context)] to run after the commit."""
    if not isinstance(payload, dict) or payload.get('object') != 'whatsapp_business_account':
        raise ValueError('Not a WhatsApp Business Account webhook.')
    counts = {'messages': 0, 'statuses': 0, 'ignored': 0, 'templates': 0}
    automation_events = []
    for entry in payload.get('entry') or []:
        for change in (entry or {}).get('changes') or []:
            field = change.get('field')
            value = change.get('value') or {}
            if field == 'message_template_status_update':
                tpl_svc.apply_status_webhook(value)
                counts['templates'] += 1
                continue
            if field != 'messages':
                counts['ignored'] += 1
                continue
            pnid = (value.get('metadata') or {}).get('phone_number_id')
            if settings.phone_number_id and pnid and str(pnid) != str(settings.phone_number_id):
                counts['ignored'] += 1     # another number on the same app
                continue
            names = {c.get('wa_id'): (c.get('profile') or {}).get('name') for c in value.get('contacts') or []}
            for m in value.get('messages') or []:
                ev = _inbound(m, names.get(m.get('from')), settings)
                if ev:
                    counts['messages'] += 1
                    automation_events.extend(ev)
            for s in value.get('statuses') or []:
                ev = _status(s)
                counts['statuses'] += 1
                automation_events.extend(ev)
            for err in value.get('errors') or []:
                core.record_error('webhook', message=f"{err.get('code')}: {err.get('title') or err.get('message')}")
    event.summary = ', '.join(f'{v} {k}' for k, v in counts.items() if v) or 'no changes'
    return automation_events


def _inbound(m, profile_name, settings):
    wamid = m.get('id')
    sender = ''.join(ch for ch in str(m.get('from') or '') if ch.isdigit())
    if not wamid or not sender:
        return []
    if WhatsAppMessage.query.filter_by(wamid=wamid).first():
        return []   # already stored (retry of a different body)
    contact = contact_svc.get_or_create(sender, profile_name)
    db.session.flush()
    is_new_conv = contact.conversation is None
    conv = contact_svc.get_or_create_conversation(contact)
    db.session.flush()

    mtype = m.get('type') or 'unknown'
    msg = WhatsAppMessage(conversation_id=conv.id, direction='in', wamid=_clip(wamid, 128), msg_type=mtype[:20],
                          status='received', timestamp=_ts(m.get('timestamp')),
                          context_wamid=_clip((m.get('context') or {}).get('id'), 128))
    extra = {}
    if mtype == 'text':
        msg.body = (m.get('text') or {}).get('body')
    elif mtype in MEDIA_TYPES:
        media = m.get(mtype) or {}
        msg.media_id = _clip(media.get('id'), 64)
        msg.media_mime = _clip(media.get('mime_type'), 100)
        msg.media_filename = _clip(media.get('filename'), 255)
        msg.body = media.get('caption')
        if mtype == 'audio' and media.get('voice'):
            msg.msg_type = 'voice'
    elif mtype == 'location':
        loc = m.get('location') or {}
        extra = {k: loc.get(k) for k in ('latitude', 'longitude', 'name', 'address')}
        msg.body = ' - '.join(str(x) for x in (loc.get('name'), loc.get('address')) if x) or 'Shared a location'
    elif mtype == 'contacts':
        cards = m.get('contacts') or []
        extra = {'contacts': [{'name': (c.get('name') or {}).get('formatted_name'),
                               'phones': [p.get('phone') for p in c.get('phones') or []]} for c in cards[:5]]}
        msg.body = ', '.join(x['name'] or '' for x in extra['contacts'])
    elif mtype == 'interactive':
        inter = m.get('interactive') or {}
        reply = inter.get('button_reply') or inter.get('list_reply') or {}
        extra = {'reply_id': reply.get('id'), 'kind': inter.get('type')}
        msg.body = reply.get('title') or reply.get('description') or '[Interactive reply]'
    elif mtype == 'button':
        btn = m.get('button') or {}
        extra = {'payload': btn.get('payload')}
        msg.body = btn.get('text')
    elif mtype == 'reaction':
        react = m.get('reaction') or {}
        msg.body = react.get('emoji') or '(reaction removed)'
        msg.context_wamid = _clip(react.get('message_id'), 128)
    else:
        errs = m.get('errors') or []
        msg.body = '[Unsupported message type]'
        if errs:
            extra = {'error': _clip(errs[0].get('title') or errs[0].get('message'), 200)}
    if extra:
        msg.extra_json = json.dumps(extra)
    try:
        with db.session.begin_nested():
            db.session.add(msg)
    except IntegrityError:
        return []   # concurrent duplicate

    had_outbound = conv.last_message_direction == 'out'
    if msg.msg_type != 'reaction':
        conv.unread_count = (conv.unread_count or 0) + 1
        if conv.status == 'resolved':
            conv.status = 'open'
    if not conv.last_inbound_at or msg.timestamp > conv.last_inbound_at:
        conv.last_inbound_at = msg.timestamp
    if not conv.last_message_at or msg.timestamp >= conv.last_message_at:
        messaging.touch_conversation(conv, msg)

    # Opt-out by keyword (e.g. STOP) or the template's "Stop promotions" button.
    keywords = {k.strip().upper() for k in (settings.optout_keywords or '').split(',') if k.strip()}
    text = (msg.body or '').strip().upper()
    if (text and text in keywords) or (mtype == 'button' and text == 'STOP PROMOTIONS'):
        if not contact.is_opted_out:
            contact_svc.set_consent(contact, 'opted_out', f'Customer replied "{msg.body.strip()[:40]}"')
            core.audit('contact.opt_out', f'contact:{contact.id}', 'Opt-out keyword received', user_id=None)

    ctx = {'conversation_id': conv.id, 'contact_id': contact.id, 'message_id': None, 'wamid': wamid,
           'text': msg.body or ''}
    events = [('inbound_message', ctx)]
    if is_new_conv:
        events.append(('new_conversation', ctx))
    if had_outbound:
        events.append(('customer_reply', ctx))
    return events


def _status(s):
    wamid, status = s.get('id'), (s.get('status') or '').lower()
    if not wamid or not status:
        return []
    at = _ts(s.get('timestamp'))
    errors = s.get('errors') or []
    err = errors[0] if errors else {}
    msg = WhatsAppMessage.query.filter_by(wamid=wamid).first()
    ev = WhatsAppStatusEvent(message_id=msg.id if msg else None, wamid=wamid[:128], status=status[:12], status_at=at,
                             error_code=_clip(err.get('code'), 20), error_title=_clip(err.get('title'), 200))
    try:
        with db.session.begin_nested():
            db.session.add(ev)
    except IntegrityError:
        return []   # already applied
    if msg is None or msg.direction != 'out':
        return []

    rank = WhatsAppMessage.STATUS_RANK
    changed = False
    if status == 'failed':
        if rank.get(msg.status, 0) < rank['delivered']:
            msg.status = 'failed'
            msg.error_code = _clip(err.get('code'), 20)
            msg.error_title = _clip(err.get('title') or err.get('message'), 200)
            msg.error_detail = _clip((err.get('error_data') or {}).get('details') or err.get('message'), 500)
            changed = True
            if str(err.get('code')) == '131050':
                conv_contact = msg.conversation.contact
                contact_svc.set_consent(conv_contact, 'opted_out', 'Meta: user stopped marketing messages')
    elif status in rank and (msg.status in ('failed', 'unknown', 'sending') or rank[status] > rank.get(msg.status, 0)):
        # A late "sent" after an earlier "failed" is ignored; "unknown"/"sending" are resolved by any status.
        if msg.status != 'failed' or status in ('delivered', 'read'):
            msg.status = status
            changed = True
    if changed:
        msg.status_updated_at = datetime.utcnow()
        if msg.campaign_recipient_id:
            r = db.session.get(WhatsAppCampaignRecipient, msg.campaign_recipient_id)
            if r:
                r.status = msg.status
                r.error = msg.error_title if msg.status == 'failed' else None
                r.updated_at = datetime.utcnow()
    if changed and msg.status == 'failed':
        return [('delivery_failed', {'conversation_id': msg.conversation_id, 'message_id': msg.id,
                                     'contact_id': msg.conversation.contact_id, 'wamid': wamid,
                                     'text': msg.error_title or ''})]
    return []
