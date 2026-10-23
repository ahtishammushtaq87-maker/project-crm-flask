"""Consent-based template campaigns.

Lifecycle: draft -> (confirm) -> scheduled | running -> completed
           running <-> paused;  draft/scheduled/running/paused -> cancelled

Safeguards:
  * Only contacts who opted in, not opted out, are recipients; opt-out is
    checked again just before each send.
  * One row per (campaign, contact) - a unique constraint - so nobody gets
    the same campaign twice.
  * Sending only happens in the background job, at most
    ``campaign_rate_per_minute`` messages per minute, and only while sending is
    enabled in Settings and the connection test has passed.
  * Restart-safe: a recipient is marked "sending" (committed) before the API
    call; one left in "sending" after a crash becomes "unknown" and is never
    resent automatically.
"""
from datetime import datetime, timedelta

from sqlalchemy import func

from app import db
from app.whatsapp.models import WhatsAppCampaign, WhatsAppCampaignRecipient, WhatsAppContact
from app.whatsapp.services import contacts as contact_svc
from app.whatsapp.services import core, messaging
from app.whatsapp.services import templates as tpl_svc

MAX_RECIPIENTS = 10000
STUCK_AFTER = timedelta(minutes=10)
COUNT_STATUSES = ('pending', 'sending', 'accepted', 'sent', 'delivered', 'read', 'failed', 'skipped', 'unknown')


class CampaignError(ValueError):
    pass


def eligible_contacts(tag_filter=''):
    q = WhatsAppContact.query.filter(WhatsAppContact.consent_status == 'opted_in')
    for tag in [t.strip().lower() for t in (tag_filter or '').split(',') if t.strip()]:
        q = q.filter(WhatsAppContact.tags.like(f'%,{tag},%'))
    return q


def counts(campaign):
    rows = (db.session.query(WhatsAppCampaignRecipient.status, func.count())
            .filter_by(campaign_id=campaign.id).group_by(WhatsAppCampaignRecipient.status).all())
    c = {s: 0 for s in COUNT_STATUSES}
    c.update({s: n for s, n in rows})
    c['total'] = sum(n for _, n in rows)
    # "sent" in the summary = everything Meta accepted, whatever happened after
    c['sent_total'] = sum(c[s] for s in ('accepted', 'sent', 'delivered', 'read'))
    c['delivered_total'] = c['delivered'] + c['read']
    return c


def resolve_values(campaign, contact):
    """Campaign variables may use {contact_name} / {contact_phone}."""
    out = {}
    for k, v in campaign.params.items():
        out[k] = (v or '').replace('{contact_name}', contact.display_name).replace('{contact_phone}',
                                                                                   '+' + contact.wa_id)
    return out


def validate_draft(campaign):
    t = campaign.template
    if t is None or not t.is_approved:
        raise CampaignError('Choose an approved template.')
    missing = [f['label'] for f in tpl_svc.variables(t) if not (campaign.params.get(f['key']) or '').strip()]
    if missing:
        raise CampaignError('Fill in: ' + ', '.join(missing))


def build_recipients(campaign):
    """(Re)build the recipient list of a draft from the current eligible contacts."""
    if campaign.status != 'draft':
        raise CampaignError('Recipients can only be changed while the campaign is a draft.')
    WhatsAppCampaignRecipient.query.filter_by(campaign_id=campaign.id).delete()
    ids = [cid for (cid,) in eligible_contacts(campaign.tag_filter).with_entities(WhatsAppContact.id)
           .limit(MAX_RECIPIENTS + 1)]
    if len(ids) > MAX_RECIPIENTS:
        raise CampaignError(f'At most {MAX_RECIPIENTS} recipients per campaign. Narrow the tag filter.')
    db.session.bulk_save_objects([WhatsAppCampaignRecipient(campaign_id=campaign.id, contact_id=i) for i in ids])
    return len(ids)


def confirm(campaign, user_id, scheduled_at=None):
    settings = core.get_settings()
    if not settings or not settings.is_connected:
        raise CampaignError('Run a successful connection test in Settings before sending campaigns.')
    if not settings.campaigns_enabled:
        raise CampaignError('Campaign sending is turned off in WhatsApp > Settings > Messaging.')
    if campaign.status != 'draft':
        raise CampaignError('Only a draft can be confirmed.')
    validate_draft(campaign)
    if not campaign.recipients.count():
        raise CampaignError('This campaign has no eligible recipients.')
    now = datetime.utcnow()
    campaign.confirmed_by, campaign.confirmed_at = user_id, now
    if scheduled_at and scheduled_at > now:
        campaign.status, campaign.scheduled_at = 'scheduled', scheduled_at
    else:
        campaign.status, campaign.started_at = 'running', now
    campaign.updated_at = now


def set_status(campaign, action):
    allowed = {
        'pause': (('running', 'scheduled'), 'paused'),
        'resume': (('paused',), 'running'),
        'cancel': (('draft', 'scheduled', 'running', 'paused'), 'cancelled'),
    }
    if action not in allowed or campaign.status not in allowed[action][0]:
        raise CampaignError(f'Cannot {action} a {campaign.status} campaign.')
    if action == 'resume':
        settings = core.get_settings()
        if not settings or not settings.is_connected or not settings.campaigns_enabled:
            raise CampaignError('Sending is disabled or the connection is not verified.')
    campaign.status = allowed[action][1]
    if action == 'resume' and not campaign.started_at:
        campaign.started_at = datetime.utcnow()
    if action == 'cancel':
        WhatsAppCampaignRecipient.query.filter_by(campaign_id=campaign.id, status='pending').update(
            {'status': 'skipped', 'error': 'Campaign cancelled'}, synchronize_session=False)
        campaign.completed_at = datetime.utcnow()
    campaign.updated_at = datetime.utcnow()


def retry_failed(campaign):
    """Put definitively failed recipients back in the queue (not "unknown"
    ones - those may have been delivered). At most 3 attempts each."""
    if campaign.status not in ('completed', 'paused', 'running'):
        raise CampaignError('Retry is available for running, paused or completed campaigns.')
    n = (WhatsAppCampaignRecipient.query
         .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id, WhatsAppCampaignRecipient.status == 'failed',
                 WhatsAppCampaignRecipient.attempts < 3)
         .update({'status': 'pending', 'error': None}, synchronize_session=False))
    if n and campaign.status == 'completed':
        campaign.status, campaign.completed_at = 'running', None
    return n


def tick(now=None):
    """Background job, once a minute. Returns number of messages attempted."""
    now = now or datetime.utcnow()
    settings = core.get_settings()
    # Recover recipients stuck in "sending" (process died mid-call): never resend.
    (WhatsAppCampaignRecipient.query
     .filter(WhatsAppCampaignRecipient.status == 'sending', WhatsAppCampaignRecipient.updated_at < now - STUCK_AFTER)
     .update({'status': 'unknown', 'error': 'Interrupted while sending - outcome unknown'},
             synchronize_session=False))
    for c in WhatsAppCampaign.query.filter(WhatsAppCampaign.status == 'scheduled',
                                           WhatsAppCampaign.scheduled_at <= now).all():
        c.status, c.started_at = 'running', now
    core.commit_with_retry()
    if not settings or not settings.is_connected or not settings.campaigns_enabled:
        return 0
    budget = max(1, min(settings.campaign_rate_per_minute or 60, 1000))
    attempted = 0
    for c in WhatsAppCampaign.query.filter_by(status='running').order_by(WhatsAppCampaign.started_at).all():
        if budget <= 0:
            break
        t = c.template
        if t is None or not t.is_approved:
            c.status, c.status_message = 'failed', 'Template is no longer approved by Meta; campaign stopped.'
            core.audit('campaign.failed', f'campaign:{c.id}', c.status_message, user_id=None)
            core.commit_with_retry()
            continue
        batch = (WhatsAppCampaignRecipient.query.filter_by(campaign_id=c.id, status='pending')
                 .order_by(WhatsAppCampaignRecipient.id).limit(budget).all())
        for r in batch:
            db.session.refresh(c)
            if c.status != 'running':     # paused/cancelled from the UI meanwhile
                break
            attempted += 1
            budget -= 1
            _send_one(c, t, r)
            if _stop_for_error(c):
                break
        if not WhatsAppCampaignRecipient.query.filter(
                WhatsAppCampaignRecipient.campaign_id == c.id,
                WhatsAppCampaignRecipient.status.in_(('pending', 'sending'))).count() and c.status == 'running':
            c.status, c.completed_at = 'completed', datetime.utcnow()
            core.audit('campaign.completed', f'campaign:{c.id}', c.name, user_id=None)
        core.commit_with_retry()
    return attempted


def _send_one(c, t, r):
    contact = r.contact
    if contact is None or contact.consent_status != 'opted_in':
        r.status, r.error = 'skipped', 'Contact opted out or consent withdrawn'
        r.updated_at = datetime.utcnow()
        core.commit_with_retry()
        return
    r.status, r.attempts, r.updated_at = 'sending', (r.attempts or 0) + 1, datetime.utcnow()
    core.commit_with_retry()
    conv = contact_svc.get_or_create_conversation(contact)
    core.commit_with_retry()
    try:
        msg = messaging.send_template(conv, t, resolve_values(c, contact), user_id=None, campaign_recipient_id=r.id)
    except messaging.SendError as e:
        r.status, r.error = 'skipped', e.message[:300]
    else:
        r.message_id = msg.id
        r.status = msg.status if msg.status in ('accepted', 'failed', 'unknown') else 'accepted'
        r.error = msg.error_title if msg.status in ('failed', 'unknown') else None
        c._last_error = msg.error_code if msg.status == 'failed' else None
    r.updated_at = datetime.utcnow()
    core.commit_with_retry()


def _stop_for_error(c):
    """Pause on account-level errors instead of failing every recipient."""
    code = getattr(c, '_last_error', None)
    if code in ('190', '0', 'invalid_token', '131031', '131042', '368', '4', '130429', '80007', '131048', '132015',
                '132016'):
        c.status = 'paused'
        c.status_message = f'Paused automatically after Meta error {code}. Check Diagnostics, then resume.'
        core.audit('campaign.auto_pause', f'campaign:{c.id}', c.status_message, user_id=None)
        core.commit_with_retry()
        return True
    return False
