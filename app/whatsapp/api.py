"""JSON endpoints for the inbox (/whatsapp/api/...). Same session login and
permission checks as the pages; POSTs need the X-CSRFToken header."""
from datetime import datetime, timedelta

from flask import abort, jsonify, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.whatsapp import bp
from app.whatsapp import permissions as perm
from app.whatsapp.models import (WhatsAppContact, WhatsAppConversation, WhatsAppMessage, WhatsAppNote,
                                 WhatsAppTemplate)
from app.whatsapp.services import automations as auto_svc
from app.whatsapp.services import core, messaging
from app.whatsapp.services import contacts as contact_svc
from app.whatsapp.services import templates as tpl_svc

PAGE = 30
MSG_PAGE = 40


def _iso(dt):
    return dt.isoformat() + 'Z' if dt else None


def _conv_or_404(cid):
    conv = db.session.get(WhatsAppConversation, cid)
    if conv is None:
        abort(404)
    if not perm.can_see_conversation(conv):
        abort(403)
    return conv


def _err(message, status=400, code='error'):
    return jsonify({'ok': False, 'error': message, 'code': code}), status


def conv_json(c):
    contact = c.contact
    return {
        'id': c.id, 'contact_id': contact.id, 'name': contact.display_name, 'phone': '+' + contact.wa_id,
        'preview': c.last_message_preview or '', 'direction': c.last_message_direction,
        'last_at': _iso(c.last_message_at), 'unread': c.unread_count or 0, 'status': c.status,
        'starred': c.is_starred, 'assigned_to': c.assigned_to.username if c.assigned_to else None,
        'assigned_to_id': c.assigned_to_id, 'tags': contact.tag_list, 'window_open': c.window_open,
        'opted_out': contact.is_opted_out,
        'initials': ''.join(w[0] for w in contact.display_name.replace('+', '').split()[:2]).upper() or '#',
    }


def msg_json(m):
    d = {
        'id': m.id, 'direction': m.direction, 'type': m.msg_type, 'body': m.body or '', 'status': m.status,
        'ts': _iso(m.timestamp), 'wamid': m.wamid, 'context_wamid': m.context_wamid,
        'error': ({'code': m.error_code, 'title': m.error_title, 'detail': m.error_detail}
                  if m.status in ('failed', 'unknown') else None),
        'sent_by': m.sent_by.username if m.sent_by else (
            'Automation' if m.automation_id else ('Campaign' if m.campaign_recipient_id else None)),
        'template': m.template_name, 'extra': m.extra,
    }
    if m.media_id or m.media_local_path:
        d['media'] = {'url': url_for('whatsapp.media', message_id=m.id), 'mime': m.media_mime or '',
                      'filename': m.media_filename or '', 'size': m.media_size}
    return d


# ── Conversations ─────────────────────────────────────────────────────────

@bp.route('/api/conversations')
@login_required
@perm.require('can_view')
def api_conversations():
    a = request.args
    q = perm.visible_conversations().join(WhatsAppContact)
    f = a.get('filter', 'all')
    if f == 'unread':
        q = q.filter(WhatsAppConversation.unread_count > 0)
    elif f in WhatsAppConversation.STATUSES:
        q = q.filter(WhatsAppConversation.status == f)
    elif f == 'mine':
        q = q.filter(WhatsAppConversation.assigned_to_id == current_user.id)
    elif f == 'unassigned':
        q = q.filter(WhatsAppConversation.assigned_to_id.is_(None))
    elif f == 'starred':
        q = q.filter(WhatsAppConversation.is_starred.is_(True))
    if a.get('tag'):
        q = q.filter(WhatsAppContact.tags.like(f'%,{a["tag"].strip().lower()},%'))
    for key, op in (('from', '>='), ('to', '<')):
        if a.get(key):
            try:
                d = datetime.strptime(a[key], '%Y-%m-%d') + (timedelta(days=1) if key == 'to' else timedelta())
            except ValueError:
                continue
            col = WhatsAppConversation.last_message_at
            q = q.filter(col >= d if op == '>=' else col < d)
    if a.get('q'):
        term = a['q'].strip()[:60]
        digits = ''.join(ch for ch in term if ch.isdigit())
        conds = [WhatsAppContact.name.ilike(f'%{term}%'), WhatsAppContact.profile_name.ilike(f'%{term}%'),
                 WhatsAppConversation.last_message_preview.ilike(f'%{term}%')]
        if digits:
            conds.append(WhatsAppContact.wa_id.like(f'%{digits.lstrip("0")}%'))
        q = q.filter(or_(*conds))
    page = max(1, int(a.get('page', 1) or 1))
    rows = (q.order_by(WhatsAppConversation.last_message_at.desc().nullslast(), WhatsAppConversation.id.desc())
            .offset((page - 1) * PAGE).limit(PAGE + 1).all())
    return jsonify({'items': [conv_json(c) for c in rows[:PAGE]], 'has_more': len(rows) > PAGE, 'page': page})


@bp.route('/api/conversations/<int:cid>')
@login_required
@perm.require('can_view')
def api_conversation(cid):
    conv = _conv_or_404(cid)
    contact = conv.contact
    cust = contact.customer
    notes = WhatsAppNote.query.filter_by(contact_id=contact.id).order_by(WhatsAppNote.created_at.desc()).limit(50)
    return jsonify({
        'conversation': conv_json(conv),
        'window': messaging.window_state(conv),
        'contact': {
            'id': contact.id, 'name': contact.name or '', 'profile_name': contact.profile_name or '',
            'phone': '+' + contact.wa_id, 'email': contact.email or (cust.email if cust else '') or '',
            'consent': contact.consent_status, 'consent_source': contact.consent_source or '',
            'consent_at': _iso(contact.consent_at), 'opted_out_at': _iso(contact.opted_out_at),
            'tags': contact.tag_list, 'last_inbound_at': _iso(conv.last_inbound_at),
            'customer': ({'id': cust.id, 'name': cust.name, 'company': cust.company_name or '',
                          'url': url_for('sales.customer_profile', id=cust.id)
                          if _has_endpoint('sales.customer_profile') else None} if cust else None),
            'edit_url': url_for('whatsapp.contact_form', cid=contact.id) if perm.can('can_manage_contacts') else None,
        },
        'notes': [{'id': n.id, 'body': n.body, 'user': n.user.username if n.user else '—',
                   'at': _iso(n.created_at)} for n in notes],
        'can': {'reply': perm.can('can_reply'), 'assign': perm.can('can_assign'),
                'contacts': perm.can('can_manage_contacts')},
    })


def _has_endpoint(name):
    from flask import current_app
    return name in current_app.view_functions


@bp.route('/api/conversations/<int:cid>/messages')
@login_required
@perm.require('can_view')
def api_messages(cid):
    conv = _conv_or_404(cid)
    q = WhatsAppMessage.query.filter_by(conversation_id=conv.id)
    before = request.args.get('before', type=int)
    if before:
        q = q.filter(WhatsAppMessage.id < before)
    rows = q.order_by(WhatsAppMessage.id.desc()).limit(MSG_PAGE + 1).all()
    items = [msg_json(m) for m in reversed(rows[:MSG_PAGE])]
    # Quoted replies: include the quoted message's text when it's in this conversation.
    ctx_ids = {m['context_wamid'] for m in items if m['context_wamid']}
    quoted = {}
    if ctx_ids:
        for m in WhatsAppMessage.query.filter(WhatsAppMessage.wamid.in_(ctx_ids),
                                              WhatsAppMessage.conversation_id == conv.id):
            quoted[m.wamid] = {'body': (m.body or messaging.preview_text(m))[:160], 'direction': m.direction}
    for m in items:
        if m['context_wamid']:
            m['quoted'] = quoted.get(m['context_wamid'])
    if not before and conv.unread_count:
        messaging.mark_conversation_read(conv)
    return jsonify({'items': items, 'has_more': len(rows) > MSG_PAGE})


@bp.route('/api/poll')
@login_required
@perm.require('can_view')
def api_poll():
    """Light polling for live updates: conversations and messages changed
    since ``since`` (ISO UTC from the previous response)."""
    try:
        since = datetime.strptime(request.args.get('since', '')[:19], '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        since = datetime.utcnow() - timedelta(minutes=2)
    since = max(since, datetime.utcnow() - timedelta(hours=1))
    now = datetime.utcnow()
    convs = (perm.visible_conversations().filter(WhatsAppConversation.updated_at >= since)
             .order_by(WhatsAppConversation.updated_at.desc()).limit(50).all())
    out = {'now': now.isoformat(timespec='seconds'), 'conversations': [conv_json(c) for c in convs],
           'messages': [], 'unread_total': perm.visible_conversations().filter(
               WhatsAppConversation.unread_count > 0).count()}
    open_id = request.args.get('open', type=int)
    if open_id:
        conv = db.session.get(WhatsAppConversation, open_id)
        if conv and perm.can_see_conversation(conv):
            after = request.args.get('after', type=int) or 0
            new = (WhatsAppMessage.query.filter(WhatsAppMessage.conversation_id == open_id,
                                                or_(WhatsAppMessage.id > after,
                                                    WhatsAppMessage.status_updated_at >= since))
                   .order_by(WhatsAppMessage.id).limit(100).all())
            out['messages'] = [msg_json(m) for m in new]
            out['window'] = messaging.window_state(conv)
            if any(m.direction == 'in' and m.id > after for m in new) and request.args.get('visible') == '1':
                messaging.mark_conversation_read(conv)
    return jsonify(out)


# ── Sending ───────────────────────────────────────────────────────────────

def _send_guard(cid):
    conv = _conv_or_404(cid)
    if not perm.can('can_reply'):
        abort(403)
    return conv


def _send_result(msg):
    core.audit('message.send', f'conversation:{msg.conversation_id}', f'{msg.msg_type} -> {msg.status}', commit=True)
    ok = msg.status in ('accepted', 'sent', 'delivered', 'read')
    body = {'ok': ok, 'message': msg_json(msg)}
    if not ok:
        body['error'] = (msg.error_title or 'Not sent') + (f' — {msg.error_detail}' if msg.error_detail else '')
    return jsonify(body), (200 if ok else 502)


@bp.route('/api/conversations/<int:cid>/send', methods=['POST'])
@login_required
@perm.require('can_view')
def api_send_text(cid):
    conv = _send_guard(cid)
    data = request.get_json(silent=True) or {}
    try:
        msg = messaging.send_text(conv, data.get('text'), current_user.id, data.get('reply_to') or None)
    except messaging.SendError as e:
        return _err(e.message, e.status, e.code)
    return _send_result(msg)


@bp.route('/api/conversations/<int:cid>/send-media', methods=['POST'])
@login_required
@perm.require('can_view')
def api_send_media(cid):
    conv = _send_guard(cid)
    f = request.files.get('file')
    if not f:
        return _err('Choose a file.')
    content = f.read()
    try:
        msg = messaging.send_media(conv, content, f.filename, request.form.get('caption'), current_user.id,
                                   request.form.get('reply_to') or None)
    except messaging.SendError as e:
        return _err(e.message, e.status, e.code)
    return _send_result(msg)


@bp.route('/api/conversations/<int:cid>/send-template', methods=['POST'])
@login_required
@perm.require('can_view')
def api_send_template(cid):
    conv = _send_guard(cid)
    data = request.get_json(silent=True) or {}
    t = db.session.get(WhatsAppTemplate, int(data.get('template_id') or 0))
    if t is None:
        return _err('Choose a template.')
    try:
        msg = messaging.send_template(conv, t, data.get('values') or {}, current_user.id)
    except messaging.SendError as e:
        return _err(e.message, e.status, e.code)
    return _send_result(msg)


@bp.route('/api/messages/<int:mid>/retry', methods=['POST'])
@login_required
@perm.require('can_view')
def api_retry(mid):
    msg = db.session.get(WhatsAppMessage, mid) or abort(404)
    _send_guard(msg.conversation_id)
    data = request.get_json(silent=True) or {}
    try:
        new = messaging.retry(msg, current_user.id, bool(data.get('confirm')))
    except messaging.SendError as e:
        return _err(e.message, e.status, e.code)
    return _send_result(new)


@bp.route('/api/templates/approved')
@login_required
@perm.require('can_view')
def api_templates():
    items = (WhatsAppTemplate.query.filter_by(status='APPROVED').filter(WhatsAppTemplate.removed_at.is_(None))
             .order_by(WhatsAppTemplate.name).all())
    return jsonify({'items': [{'id': t.id, 'name': t.name, 'language': t.language, 'category': t.category,
                               'variables': tpl_svc.variables(t), 'preview': tpl_svc.render_preview(t, {})}
                              for t in items]})


@bp.route('/api/templates/<int:tid>/preview', methods=['POST'])
@login_required
@perm.require('can_view')
def api_template_preview(tid):
    t = db.session.get(WhatsAppTemplate, tid) or abort(404)
    values = (request.get_json(silent=True) or {}).get('values') or {}
    return jsonify({'preview': tpl_svc.render_preview(t, values)})


# ── Conversation management ───────────────────────────────────────────────

@bp.route('/api/conversations/<int:cid>/update', methods=['POST'])
@login_required
@perm.require('can_view')
def api_update(cid):
    conv = _conv_or_404(cid)
    data = request.get_json(silent=True) or {}
    changed = []
    if 'status' in data:
        if data['status'] not in WhatsAppConversation.STATUSES or not perm.can('can_reply'):
            abort(400 if perm.can('can_reply') else 403)
        conv.status = data['status']
        changed.append(f'status={conv.status}')
    if 'starred' in data:
        conv.is_starred = bool(data['starred'])
        changed.append('starred' if conv.is_starred else 'unstarred')
    assigned_event = None
    if 'assigned_to_id' in data:
        if not perm.can('can_assign'):
            abort(403)
        from app.models import User
        uid = data['assigned_to_id']
        if uid not in (None, '') and not db.session.get(User, int(uid)):
            return _err('Unknown user.')
        new_uid = int(uid) if uid not in (None, '') else None
        if new_uid != conv.assigned_to_id:
            conv.assigned_to_id = new_uid
            changed.append(f'assigned_to={new_uid}')
            if new_uid:
                assigned_event = new_uid
    if 'tags' in data:
        if not perm.can('can_reply') and not perm.can('can_manage_contacts'):
            abort(403)
        conv.contact.set_tags(data['tags'] if isinstance(data['tags'], list) else str(data['tags']).split(','))
        changed.append('tags')
    if not changed:
        return _err('Nothing to change.')
    conv.updated_at = datetime.utcnow()
    core.audit('conversation.update', f'conversation:{conv.id}', ', '.join(changed)[:500])
    core.commit_with_retry()
    if assigned_event:
        auto_svc.emit('conversation_assigned', {
            'conversation_id': conv.id, 'contact_id': conv.contact_id, 'text': '',
            'event_key': f'assigned:{conv.id}:{assigned_event}:{int(datetime.utcnow().timestamp())}'})
        _notify_assignee(conv, assigned_event)
    db.session.refresh(conv)
    if not perm.can_see_conversation(conv):
        return jsonify({'ok': True, 'removed': True})
    return jsonify({'ok': True, 'conversation': conv_json(conv)})


def _notify_assignee(conv, user_id):
    s = core.get_settings()
    if not s or not s.notify_assigned_by_email or user_id == current_user.id:
        return
    from app.models import User
    from app.system_mail import mailer
    user = db.session.get(User, user_id)
    if user and user.email:
        link = core.external_url('whatsapp.inbox', c=conv.id)
        mailer.send_email(user.email, f'WhatsApp conversation assigned to you: {conv.contact.display_name}',
                          f'{current_user.username} assigned you the WhatsApp conversation with '
                          f'{conv.contact.display_name}.\n\n{link}')


@bp.route('/api/conversations/<int:cid>/notes', methods=['POST'])
@login_required
@perm.require('can_view')
def api_add_note(cid):
    conv = _conv_or_404(cid)
    body = ((request.get_json(silent=True) or {}).get('body') or '').strip()
    if not body:
        return _err('Write a note first.')
    note = WhatsAppNote(contact_id=conv.contact_id, user_id=current_user.id, body=body[:5000])
    db.session.add(note)
    core.commit_with_retry()
    return jsonify({'ok': True, 'note': {'id': note.id, 'body': note.body, 'user': current_user.username,
                                         'at': _iso(note.created_at)}})


@bp.route('/api/contacts/search')
@login_required
@perm.require('can_view')
def api_contact_search():
    """For "new conversation": contacts the user may message."""
    if not perm.can('can_reply'):
        abort(403)
    term = (request.args.get('q') or '').strip()
    rows = contact_svc.search(term).order_by(WhatsAppContact.last_message_at.desc().nullslast()).limit(15).all()
    return jsonify({'items': [{'id': c.id, 'name': c.display_name, 'phone': '+' + c.wa_id,
                               'consent': c.consent_status} for c in rows]})


@bp.route('/api/customers/search')
@login_required
@perm.require('can_manage_contacts')
def api_customer_search():
    """CRM customers for the "linked customer" picker (name, company or phone)."""
    if not (perm.is_admin() or getattr(current_user, 'can_view_customers', False)):
        abort(403)
    from app.models import Customer
    term = (request.args.get('q') or '').strip()[:60]
    if len(term) < 2:
        return jsonify({'items': []})
    like = f'%{term}%'
    rows = (Customer.query.filter(or_(Customer.name.ilike(like), Customer.company_name.ilike(like),
                                      Customer.phone.ilike(like)))
            .order_by(Customer.name).limit(20).all())
    return jsonify({'items': [{'id': c.id, 'text': c.name + (f' ({c.phone})' if c.phone else '')} for c in rows]})


@bp.route('/api/contacts/<int:contact_id>/open', methods=['POST'])
@login_required
@perm.require('can_view')
def api_contact_open(contact_id):
    if not perm.can('can_reply'):
        abort(403)
    contact = db.session.get(WhatsAppContact, contact_id) or abort(404)
    conv = contact_svc.get_or_create_conversation(contact)
    if not conv.assigned_to_id and not perm.can('can_view_all'):
        conv.assigned_to_id = current_user.id
    core.commit_with_retry()
    if not perm.can_see_conversation(conv):
        return _err('This conversation is assigned to someone else.', 403)
    return jsonify({'ok': True, 'conversation': conv_json(conv)})
