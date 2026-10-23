"""Simple automations: one trigger, optional conditions, one action.

Safety rules:
  * New automations start disabled and in dry-run (test) mode; a dry run only
    writes a log line describing what it would have done.
  * Each (automation, event) pair runs at most once - a unique log row is
    claimed before the action runs, so webhook retries or two workers can't
    double-send.
  * Actions never emit new events, so automations can't trigger each other.
  * Sending a template needs an approved template and a contact who has
    opted in; anything else is logged as skipped.
  * CRM triggers (invoices/payments) come from a background scan of the
    existing tables - the invoice and payment code is not changed - and only
    consider invoices created / due / paid after the automation was created,
    so enabling one never messages old customers in bulk.
"""
import json
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app import db
from app.whatsapp.models import (WhatsAppAutomation, WhatsAppAutomationLog, WhatsAppContact,
                                 WhatsAppConversation, WhatsAppTemplate)
from app.whatsapp.services import core

TRIGGERS = {
    'inbound_message': 'New inbound WhatsApp message',
    'new_conversation': 'New conversation (first message from a number)',
    'customer_reply': 'Customer replies to our message',
    'conversation_assigned': 'Conversation assigned to someone',
    'delivery_failed': 'Message delivery failed',
    'invoice_created': 'Invoice created',
    'invoice_overdue': 'Invoice overdue',
    'payment_received': 'Invoice fully paid',
}
MESSAGE_TRIGGERS = ('inbound_message', 'new_conversation', 'customer_reply')
CRM_TRIGGERS = ('invoice_created', 'invoice_overdue', 'payment_received')

ACTIONS = {
    'notify_staff': 'Email the assigned staff member (uses Settings > Email)',
    'create_task': 'Create a CRM task',
    'assign_conversation': 'Assign the conversation',
    'add_tag': 'Add a tag to the contact',
    'send_template': 'Send an approved WhatsApp template',
}

PLACEHOLDERS = ('contact_name', 'contact_phone', 'invoice_number', 'invoice_total', 'invoice_balance',
                'invoice_due_date', 'invoice_link', 'message_text')


class AutomationError(ValueError):
    pass


def validate(form):
    """Build (fields dict) from a submitted builder form, or raise AutomationError."""
    name = (form.get('name') or '').strip()[:150]
    trigger, action = form.get('trigger'), form.get('action')
    if not name:
        raise AutomationError('Give the automation a name.')
    if trigger not in TRIGGERS:
        raise AutomationError('Choose a trigger.')
    if action not in ACTIONS:
        raise AutomationError('Choose an action.')
    if action == 'assign_conversation' and trigger in CRM_TRIGGERS:
        raise AutomationError('Invoice triggers have no conversation to assign.')
    conditions = {}
    if (form.get('cond_keyword') or '').strip():
        conditions['keyword'] = form['cond_keyword'].strip()[:100]
    if (form.get('cond_tag') or '').strip():
        conditions['tag'] = form['cond_tag'].strip().lower()[:30]
    config = {}
    user_id = form.get('cfg_user_id')
    if user_id and str(user_id).isdigit():
        config['user_id'] = int(user_id)
    if action == 'assign_conversation' and 'user_id' not in config:
        raise AutomationError('Choose who to assign to.')
    if action == 'add_tag':
        tag = (form.get('cfg_tag') or '').strip().lower()[:30]
        if not tag:
            raise AutomationError('Enter the tag to add.')
        config['tag'] = tag
    if action == 'create_task':
        config['title'] = (form.get('cfg_title') or '').strip()[:100] or 'Follow up WhatsApp: {contact_name}'
        config['priority'] = form.get('cfg_priority') if form.get('cfg_priority') in (
            'Low', 'Medium', 'High', 'Critical') else 'Medium'
        try:
            config['due_days'] = max(0, min(60, int(form.get('cfg_due_days') or 1)))
        except ValueError:
            config['due_days'] = 1
    if action == 'send_template':
        tid = form.get('cfg_template_id')
        t = db.session.get(WhatsAppTemplate, int(tid)) if tid and str(tid).isdigit() else None
        if t is None or not t.is_approved:
            raise AutomationError('Choose an approved template.')
        config['template_id'] = t.id
        from app.whatsapp.services import templates as tpl_svc
        config['values'] = {f['key']: (form.get('cfg_var_' + f['key']) or '').strip()[:500]
                            for f in tpl_svc.variables(t)}
        missing = [k for k, v in config['values'].items() if not v]
        if missing:
            raise AutomationError('Fill every template variable (you can use placeholders like {contact_name}).')
    return {'name': name, 'trigger': trigger, 'action': action,
            'conditions_json': json.dumps(conditions), 'action_config_json': json.dumps(config)}


# ── Running ───────────────────────────────────────────────────────────────

def run_events(app, events):
    with app.app_context():
        try:
            handle_events(events)
        except Exception:
            db.session.rollback()
            app.logger.exception('WhatsApp automations failed')
        finally:
            db.session.remove()


def handle_events(events):
    for trigger, ctx in events:
        autos = WhatsAppAutomation.query.filter_by(trigger=trigger, is_enabled=True).all()
        for a in autos:
            run_one(a, trigger, ctx)


def emit(trigger, ctx):
    """Entry point for events raised by CRM staff actions (e.g. assignment).
    Runs synchronously; failures are logged, never raised to the user."""
    try:
        handle_events([(trigger, ctx)])
    except Exception:
        db.session.rollback()


def _event_key(trigger, ctx):
    if ctx.get('event_key'):
        return ctx['event_key'][:120]
    if ctx.get('wamid'):
        return f'{trigger}:{ctx["wamid"]}'[:120]
    if ctx.get('sale_id'):
        return f'{trigger}:sale:{ctx["sale_id"]}'
    return f'{trigger}:{ctx.get("conversation_id")}:{datetime.utcnow().isoformat()}'


def run_one(a, trigger, ctx, force_dry_run=False):
    key = _event_key(trigger, ctx)
    log = WhatsAppAutomationLog(automation_id=a.id, event_key=key, result='skipped')
    try:
        with db.session.begin_nested():
            db.session.add(log)      # claim: unique (automation, event)
    except IntegrityError:
        return None
    contact = db.session.get(WhatsAppContact, ctx['contact_id']) if ctx.get('contact_id') else None
    conv = db.session.get(WhatsAppConversation, ctx['conversation_id']) if ctx.get('conversation_id') else None
    if conv is None and contact is not None:
        conv = contact.conversation
    ok, why = _conditions_met(a.conditions, ctx, contact)
    if not ok:
        log.detail = why
    elif a.dry_run or force_dry_run:
        log.result = 'dry_run'
        log.detail = ('Would: ' + describe(a, contact, ctx))[:500]
    else:
        try:
            log.result, log.detail = _execute(a, ctx, contact, conv)
        except Exception as e:  # never break the caller (webhook / scheduler)
            db.session.rollback()
            log = WhatsAppAutomationLog(automation_id=a.id, event_key=key, result='error',
                                        detail=str(e)[:500])
            try:
                with db.session.begin_nested():
                    db.session.add(log)
            except IntegrityError:
                pass
    a.last_run_at = datetime.utcnow()
    core.commit_with_retry()
    return log


def _conditions_met(cond, ctx, contact):
    kw = cond.get('keyword')
    if kw and kw.lower() not in (ctx.get('text') or '').lower():
        return False, f'Message does not contain "{kw}"'
    tag = cond.get('tag')
    if tag and (contact is None or tag not in contact.tag_list):
        return False, f'Contact does not have tag "{tag}"'
    return True, ''


def describe(a, contact=None, ctx=None):
    cfg = a.config
    who = contact.display_name if contact else 'the contact'
    if a.action == 'send_template':
        t = db.session.get(WhatsAppTemplate, cfg.get('template_id'))
        return f'send template "{t.name if t else "?"}" to {who}'
    if a.action == 'add_tag':
        return f'add tag "{cfg.get("tag")}" to {who}'
    if a.action == 'assign_conversation':
        return f'assign the conversation with {who} to user #{cfg.get("user_id")}'
    if a.action == 'create_task':
        return f'create task "{_fill(cfg.get("title", ""), contact, ctx or {})}"'
    return f'email the assigned staff member about {who}'


def _vars(contact, ctx):
    from app.models import Sale
    v = {'contact_name': contact.display_name if contact else '',
         'contact_phone': '+' + contact.wa_id if contact else '', 'message_text': (ctx.get('text') or '')[:200]}
    sale = db.session.get(Sale, ctx['sale_id']) if ctx.get('sale_id') else None
    if sale is not None:
        v['invoice_number'] = sale.invoice_number
        v['invoice_total'] = f'{sale.total or 0:,.2f}'
        v['invoice_balance'] = f'{max(0.0, (sale.total or 0) - (sale.paid_amount or 0)):,.2f}'
        v['invoice_due_date'] = sale.due_date.strftime('%d %b %Y') if sale.due_date else ''
        # The CRM's existing public share link (token expires after 30 days).
        v['invoice_link'] = core.external_url('sales.public_invoice', token=sale.valid_access_token)
    return v


def _fill(text, contact, ctx):
    values = _vars(contact, ctx)
    for k in PLACEHOLDERS:
        text = text.replace('{' + k + '}', str(values.get(k, '')))
    return text


def _execute(a, ctx, contact, conv):
    cfg = a.config
    if a.action == 'add_tag':
        if contact is None:
            return 'skipped', 'No WhatsApp contact for this event'
        contact.set_tags(contact.tag_list + [cfg['tag']])
        return 'done', f'Tag "{cfg["tag"]}" added to {contact.display_name}'

    if a.action == 'assign_conversation':
        if conv is None:
            return 'skipped', 'No conversation for this event'
        if conv.assigned_to_id:
            return 'skipped', 'Conversation is already assigned'
        conv.assigned_to_id = cfg['user_id']
        core.audit('conversation.assign', f'conversation:{conv.id}', f'By automation "{a.name}"', user_id=None)
        return 'done', f'Assigned to user #{cfg["user_id"]}'

    if a.action == 'create_task':
        from app.models import Task
        assignee = cfg.get('user_id') or (conv.assigned_to_id if conv else None) or (
            contact.assigned_to_id if contact else None) or a.created_by
        if not assignee or not a.created_by:
            return 'skipped', 'Nobody to assign the task to'
        link = ''
        if conv is not None:
            url = core.external_url('whatsapp.inbox', c=conv.id)
            link = ('\n\nOpen in WhatsApp inbox: ' + url) if url else ''
        task = Task(title=_fill(cfg.get('title') or 'WhatsApp follow-up', contact, ctx)[:100],
                    description=(f'Created by WhatsApp automation "{a.name}".\n'
                                 f'{(ctx.get("text") or "")[:500]}{link}'),
                    priority=cfg.get('priority', 'Medium'), status='Pending',
                    due_date=datetime.utcnow() + timedelta(days=cfg.get('due_days', 1)),
                    assigned_to_id=assignee, created_by_id=a.created_by,
                    linked_invoice_id=ctx.get('sale_id'))
        db.session.add(task)
        return 'done', f'Task created for user #{assignee}'

    if a.action == 'notify_staff':
        from app.models import User
        uid = cfg.get('user_id') or (conv.assigned_to_id if conv else None) or (
            contact.assigned_to_id if contact else None)
        user = db.session.get(User, uid) if uid else None
        if user is None or not user.email:
            return 'skipped', 'No assigned staff member with an email address'
        from app.system_mail import mailer
        who = contact.display_name if contact else 'a customer'
        body = (f'WhatsApp automation "{a.name}": {TRIGGERS.get(a.trigger)} - {who}.\n\n'
                f'{(ctx.get("text") or "")[:500]}\n\nThis email does not contain the full conversation; '
                f'open the CRM WhatsApp inbox to reply.')
        ok, msg = mailer.send_email(user.email, f'WhatsApp: {TRIGGERS.get(a.trigger)} - {who}', body)
        return ('done' if ok else 'error'), msg[:500]

    if a.action == 'send_template':
        from app.whatsapp.services import contacts as contact_svc, messaging
        if contact is None:
            return 'skipped', 'No WhatsApp contact linked to this customer'
        if contact.consent_status != 'opted_in':
            return 'skipped', f'{contact.display_name} has not opted in to WhatsApp messages'
        t = db.session.get(WhatsAppTemplate, cfg.get('template_id'))
        if t is None or not t.is_approved:
            return 'skipped', 'Template is missing or no longer approved'
        values = {k: _fill(v, contact, ctx) for k, v in (cfg.get('values') or {}).items()}
        conv = conv or contact_svc.get_or_create_conversation(contact)
        core.commit_with_retry()
        try:
            msg = messaging.send_template(conv, t, values, user_id=None, automation_id=a.id)
        except messaging.SendError as e:
            return 'skipped', e.message
        return ('done' if msg.status != 'failed' else 'error'), f'Template "{t.name}": {msg.status}'
    return 'skipped', 'Unknown action'


# ── CRM scan (background job) ─────────────────────────────────────────────

def scan_crm_events():
    """Turn invoice/payment changes in the existing CRM tables into automation
    events. Read-only on those tables."""
    from app.models import Sale
    autos = WhatsAppAutomation.query.filter(WhatsAppAutomation.is_enabled.is_(True),
                                            WhatsAppAutomation.trigger.in_(CRM_TRIGGERS)).all()
    if not autos:
        return 0
    count = 0
    by_trigger = {}
    for a in autos:
        by_trigger.setdefault(a.trigger, []).append(a)

    def contact_for(sale):
        if not sale.customer_id:
            return None
        return (WhatsAppContact.query.filter_by(customer_id=sale.customer_id)
                .order_by(WhatsAppContact.last_message_at.desc().nullslast()).first())

    base = Sale.query.filter(Sale.is_draft.isnot(True), Sale.is_rejected.isnot(True))
    for trigger, items in by_trigger.items():
        since = min(a.created_at for a in items)
        if trigger == 'invoice_created':
            sales = base.filter(Sale.created_at >= since).order_by(Sale.id.desc()).limit(200).all()
        elif trigger == 'invoice_overdue':
            sales = (base.filter(Sale.status.in_(('unpaid', 'partial')), Sale.due_date.isnot(None),
                                 Sale.due_date < datetime.utcnow(), Sale.due_date >= since)
                     .order_by(Sale.due_date.desc()).limit(200).all())
        else:
            sales = (base.filter(Sale.status == 'paid', Sale.updated_at >= since)
                     .order_by(Sale.updated_at.desc()).limit(200).all())
        for sale in sales:
            contact = contact_for(sale)
            ctx = {'sale_id': sale.id, 'customer_id': sale.customer_id,
                   'contact_id': contact.id if contact else None,
                   'text': f'Invoice {sale.invoice_number}'}
            for a in items:
                anchor = {'invoice_created': sale.created_at, 'invoice_overdue': sale.due_date,
                          'payment_received': sale.updated_at}[trigger]
                if anchor and anchor >= a.created_at:
                    if run_one(a, trigger, ctx) is not None:
                        count += 1
    return count
