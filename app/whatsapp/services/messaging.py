"""Sending messages and applying Meta's messaging rules.

Every send follows the same steps: check the rules, save the outgoing message
as "sending", commit, call Meta, then store Meta's message id ("accepted").
Delivery/read/failed arrive later through the webhook. If the API call times
out the message becomes "unknown" - Meta may or may not have it - and it is
never resent automatically; a person can retry it after checking.

Rules enforced here (server side, whatever the browser shows):
  * Free-form messages (text/media) only inside the 24-hour customer service
    window that starts with the customer's last inbound message.
  * Outside the window only an APPROVED template can be sent.
  * No business-initiated (template) message to an opted-out contact.
"""
import json
import os
import uuid
from datetime import datetime

from app import db
from app.whatsapp import media_root
from app.whatsapp.models import WhatsAppConversation, WhatsAppMessage
from app.whatsapp.services import core, templates as tpl_svc
from app.whatsapp.services.cloud_api import ApiError

MAX_TEXT = 4096

# Cloud API supported media (https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media)
MEDIA_RULES = {
    'image': ({'image/jpeg': '.jpg', 'image/png': '.png'}, 5),
    'video': ({'video/mp4': '.mp4', 'video/3gpp': '.3gp'}, 16),
    'audio': ({'audio/aac': '.aac', 'audio/amr': '.amr', 'audio/mpeg': '.mp3', 'audio/mp4': '.m4a',
               'audio/ogg': '.ogg'}, 16),
    'document': ({'application/pdf': '.pdf', 'text/plain': '.txt', 'application/msword': '.doc',
                  'application/vnd.ms-excel': '.xls', 'application/vnd.ms-powerpoint': '.ppt',
                  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
                  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
                  'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx'}, 100),
}
EXT_TO_MIME = {ext: mime for rules, _ in MEDIA_RULES.values() for mime, ext in rules.items()}
EXT_TO_MIME.update({'.jpeg': 'image/jpeg', '.opus': 'audio/ogg', '.mpeg': 'audio/mpeg'})


class SendError(Exception):
    def __init__(self, message, code='blocked', status=400):
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


# ── Rules ─────────────────────────────────────────────────────────────────

def window_state(conv):
    exp = conv.window_expires_at
    return {'open': conv.window_open,
            'expires_at': exp.isoformat() + 'Z' if exp else None,
            'last_inbound_at': conv.last_inbound_at.isoformat() + 'Z' if conv.last_inbound_at else None}


def _require_configured(settings):
    if not settings or not settings.phone_number_id or not settings.access_token_enc:
        raise SendError('WhatsApp is not connected yet. An administrator must add the credentials in '
                        'WhatsApp > Settings.', 'not_configured')


def check_free_form(conv):
    if not conv.window_open:
        raise SendError('The 24-hour customer service window is closed (the customer has not messaged in the '
                        'last 24 hours). Send an approved template instead.', 'window_closed')


def check_template_allowed(conv, template):
    if not template.is_approved:
        raise SendError(f'Template "{template.name}" is not approved by Meta ({template.status}).', 'not_approved')
    if conv.contact.is_opted_out:
        raise SendError('This contact has opted out of WhatsApp messages. Business-initiated messages are blocked.',
                        'opted_out')


# ── Media validation ──────────────────────────────────────────────────────

def sniff_mime(head, filename):
    ext = os.path.splitext(filename or '')[1].lower()
    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if head.startswith(b'%PDF-'):
        return 'application/pdf'
    if head.startswith(b'OggS'):
        return 'audio/ogg'
    if head.startswith(b'#!AMR'):
        return 'audio/amr'
    if head.startswith(b'ID3') or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0
                                   and head[1] & 0x06 != 0):
        return 'audio/mpeg'
    if len(head) > 1 and head[0] == 0xFF and head[1] in (0xF1, 0xF9):
        return 'audio/aac'
    if head[4:8] == b'ftyp':
        brand = head[8:12]
        if brand.startswith(b'3g'):
            return 'video/3gpp'
        if brand in (b'M4A ', b'M4B '):
            return 'audio/mp4'
        return 'audio/mp4' if ext == '.m4a' else 'video/mp4'
    if head.startswith(b'PK\x03\x04') and ext in ('.docx', '.xlsx', '.pptx'):
        return EXT_TO_MIME[ext]
    if head.startswith(b'\xd0\xcf\x11\xe0') and ext in ('.doc', '.xls', '.ppt'):
        return EXT_TO_MIME[ext]
    if ext == '.txt':
        try:
            head.decode('utf-8')
            return 'text/plain'
        except UnicodeDecodeError:
            return None
    return None


def validate_upload(content, filename, max_upload_mb):
    """Returns (msg_type, mime). The type comes from the file's bytes, not the
    browser's claim."""
    if not content:
        raise SendError('The file is empty.')
    mime = sniff_mime(content[:64], filename)
    if not mime:
        raise SendError('This file type is not supported by WhatsApp. Use JPG/PNG images, MP4/3GP video, '
                        'AAC/AMR/MP3/M4A/OGG audio, or PDF/Word/Excel/PowerPoint/TXT documents.')
    for msg_type, (mimes, limit_mb) in MEDIA_RULES.items():
        if mime in mimes:
            limit = min(limit_mb, max_upload_mb or limit_mb) * 1024 * 1024
            if len(content) > limit:
                raise SendError(f'{msg_type.title()} files can be at most {limit // (1024 * 1024)} MB.')
            return msg_type, mime
    raise SendError('Unsupported file type.')


def safe_filename(name):
    base = os.path.basename(name or 'file').replace('\\', '_')
    keep = ''.join(ch for ch in base if ch.isalnum() or ch in ' ._-()')[:120].strip()
    return keep or 'file'


# ── Conversation bookkeeping ──────────────────────────────────────────────

def preview_text(msg):
    if msg.msg_type == 'text' and msg.body:
        return msg.body[:200]
    if msg.msg_type == 'template':
        return ('Template: ' + (msg.template_name or ''))[:200]
    label = {'image': 'Photo', 'video': 'Video', 'audio': 'Audio', 'voice': 'Voice message', 'document': 'Document',
             'sticker': 'Sticker', 'location': 'Location', 'contacts': 'Contact card', 'reaction': 'Reaction',
             'interactive': 'Reply', 'button': 'Button reply'}.get(msg.msg_type, msg.msg_type.title())
    return (f'[{label}] ' + (msg.body or msg.media_filename or '')).strip()[:200]


def touch_conversation(conv, msg):
    conv.last_message_at = msg.timestamp
    conv.last_message_preview = preview_text(msg)
    conv.last_message_direction = msg.direction
    conv.updated_at = datetime.utcnow()
    if msg.direction == 'out' and msg.sent_by_id and conv.first_response_at is None and conv.last_inbound_at:
        conv.first_response_at = msg.timestamp
    conv.contact.last_message_at = msg.timestamp


# ── Sending ───────────────────────────────────────────────────────────────

def _new_outgoing(conv, msg_type, user_id=None, **fields):
    msg = WhatsAppMessage(conversation_id=conv.id, direction='out', msg_type=msg_type, status='sending',
                          client_ref=str(uuid.uuid4()), sent_by_id=user_id, timestamp=datetime.utcnow(), **fields)
    db.session.add(msg)
    touch_conversation(conv, msg)
    core.commit_with_retry()   # saved before calling Meta, so nothing is lost if the call hangs
    return msg


def _dispatch(conv, msg, content, settings):
    try:
        wamid = core.api(settings).send_message(conv.contact.wa_id, 'template' if msg.msg_type == 'template'
                                                else msg.msg_type, content, msg.context_wamid)
    except ApiError as e:
        if e.uncertain:
            msg.status = 'unknown'
            msg.error_title = 'Outcome unknown'
            msg.error_detail = (e.message + ' Check with the customer before retrying.')[:500]
        else:
            msg.status = 'failed'
            msg.error_code = str(e.code or e.kind)[:20]
            msg.error_title = e.label[:200]
            msg.error_detail = e.message[:500]
            if e.kind == 'user_opted_out_marketing':
                from app.whatsapp.services import contacts as contact_svc
                contact_svc.set_consent(conv.contact, 'opted_out', 'Meta: user stopped marketing messages')
        msg.status_updated_at = datetime.utcnow()
        core.record_error('send', e)
        core.commit_with_retry()
        return msg
    msg.wamid = wamid
    msg.status = 'accepted'
    msg.status_updated_at = datetime.utcnow()
    core.commit_with_retry()
    return msg


def send_text(conv, text, user_id=None, reply_to_wamid=None):
    settings = core.get_settings()
    _require_configured(settings)
    text = (text or '').strip()
    if not text:
        raise SendError('Type a message first.')
    if len(text) > MAX_TEXT:
        raise SendError(f'Messages can be at most {MAX_TEXT} characters.')
    check_free_form(conv)
    msg = _new_outgoing(conv, 'text', user_id, body=text, context_wamid=reply_to_wamid or None)
    return _dispatch(conv, msg, {'body': text, 'preview_url': 'http' in text}, settings)


def send_media(conv, content, filename, caption=None, user_id=None, reply_to_wamid=None):
    settings = core.get_settings()
    _require_configured(settings)
    check_free_form(conv)
    msg_type, mime = validate_upload(content, filename, settings.max_upload_mb)
    filename = safe_filename(filename)
    caption = (caption or '').strip()[:1024]
    if caption and msg_type == 'audio':
        raise SendError('Audio messages cannot have a caption.')
    # Keep a private copy so staff can preview what was sent (cleaned up by retention).
    rel = os.path.join('out', uuid.uuid4().hex + MEDIA_RULES[msg_type][0][mime])
    path = os.path.join(media_root(), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(content)
    msg = _new_outgoing(conv, msg_type, user_id, body=caption or None, media_mime=mime, media_filename=filename,
                        media_size=len(content), media_local_path=rel, context_wamid=reply_to_wamid or None)
    try:
        media_id = core.api(settings).upload_media(content, mime, filename)
    except ApiError as e:
        msg.status, msg.error_code = 'failed', str(e.code or e.kind)[:20]
        msg.error_title, msg.error_detail = 'Upload to WhatsApp failed', e.message[:500]
        msg.status_updated_at = datetime.utcnow()
        core.record_error('media', e)
        core.commit_with_retry()
        return msg
    msg.media_id = media_id
    payload = {'id': media_id}
    if caption:
        payload['caption'] = caption
    if msg_type == 'document':
        payload['filename'] = filename
    return _dispatch(conv, msg, payload, settings)


def send_template(conv, template, values, user_id=None, automation_id=None, campaign_recipient_id=None):
    settings = core.get_settings()
    _require_configured(settings)
    check_template_allowed(conv, template)
    try:
        payload, clean = tpl_svc.build_payload(template, values or {})
    except tpl_svc.TemplateError as e:
        raise SendError(str(e), 'template_params')
    msg = _new_outgoing(conv, 'template', user_id, body=tpl_svc.render_preview(template, clean),
                        template_name=template.name, template_language=template.language,
                        template_params=json.dumps(clean), automation_id=automation_id,
                        campaign_recipient_id=campaign_recipient_id)
    return _dispatch(conv, msg, payload, settings)


def retry(msg, user_id, confirm_uncertain=False):
    """Send a failed (or, after explicit confirmation, unknown) message again as
    a new message. The original keeps its history."""
    if msg.direction != 'out' or msg.status not in ('failed', 'unknown'):
        raise SendError('Only failed messages can be retried.')
    if msg.status == 'unknown' and not confirm_uncertain:
        raise SendError('This message may already have reached the customer. Confirm to send it again.',
                        'confirm_needed', 409)
    if WhatsAppMessage.query.filter_by(retry_of_id=msg.id).filter(
            WhatsAppMessage.status.notin_(('failed',))).first():
        raise SendError('This message was already retried.')
    conv = db.session.get(WhatsAppConversation, msg.conversation_id)
    if msg.msg_type == 'text':
        new = send_text(conv, msg.body, user_id, msg.context_wamid)
    elif msg.msg_type == 'template':
        from app.whatsapp.models import WhatsAppTemplate
        t = WhatsAppTemplate.query.filter_by(name=msg.template_name, language=msg.template_language).first()
        if t is None:
            raise SendError('That template no longer exists.')
        new = send_template(conv, t, msg.params, user_id)
    elif msg.media_local_path:
        path = os.path.join(media_root(), msg.media_local_path)
        if not os.path.isfile(path):
            raise SendError('The original file is no longer stored; attach it again.')
        with open(path, 'rb') as fh:
            new = send_media(conv, fh.read(), msg.media_filename, msg.body, user_id, msg.context_wamid)
    else:
        raise SendError('This message type cannot be retried.')
    new.retry_of_id = msg.id
    core.commit_with_retry()
    return new


def mark_conversation_read(conv):
    """Clear the unread badge; tell Meta (blue ticks) for the newest inbound
    message when enabled. A Meta error here never blocks the inbox."""
    had_unread = conv.unread_count
    conv.unread_count = 0
    core.commit_with_retry()
    settings = core.get_settings()
    if not had_unread or not settings or not settings.auto_mark_read or not settings.access_token_enc:
        return
    last_in = (WhatsAppMessage.query.filter_by(conversation_id=conv.id, direction='in')
               .filter(WhatsAppMessage.wamid.isnot(None)).order_by(WhatsAppMessage.id.desc()).first())
    if last_in and last_in.status != 'read':
        try:
            core.api(settings).mark_read(last_in.wamid)
            last_in.status = 'read'
            core.commit_with_retry()
        except ApiError as e:
            core.record_error('send', e, 'Mark as read failed: ' + e.message, commit=True)
