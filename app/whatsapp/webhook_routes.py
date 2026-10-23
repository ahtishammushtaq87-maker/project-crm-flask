"""/webhooks/whatsapp - called by Meta, server to server.

No CRM login (Meta can't sign in) and no form CSRF token: GET is protected by
the verify token, POST by the X-Hub-Signature-256 HMAC of the raw body with
the Meta App Secret, compared in constant time.
"""
import hmac
import json
import threading
from datetime import datetime

from flask import current_app, request

from app import db
from app.whatsapp import webhook_bp
from app.whatsapp.services import core, security
from app.whatsapp.services import webhooks as webhook_svc

MAX_BODY = 3 * 1024 * 1024


@webhook_bp.route('/webhooks/whatsapp', methods=['GET'])
def verify():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token') or ''
    challenge = request.args.get('hub.challenge') or ''
    settings = core.get_settings()
    try:
        expected = security.decrypt(settings.verify_token_enc) if settings else ''
    except security.SecretUnavailable:
        expected = ''
    if mode == 'subscribe' and expected and hmac.compare_digest(token.encode(), expected.encode()) \
            and challenge and len(challenge) <= 200:
        return challenge, 200, {'Content-Type': 'text/plain'}
    core.record_error('webhook', message='Webhook verification rejected (wrong verify token or mode).', commit=True)
    return 'Verification failed', 403


@webhook_bp.route('/webhooks/whatsapp', methods=['POST'])
def receive():
    if (request.content_length or 0) > MAX_BODY:
        return 'Payload too large', 413
    raw = request.get_data(cache=False, as_text=False)
    settings = core.get_settings()
    try:
        secret = security.decrypt(settings.app_secret_enc) if settings else ''
    except security.SecretUnavailable:
        secret = ''
    if not secret:
        core.record_error('webhook', message='Webhook received but no App Secret is saved; event rejected.',
                          commit=True)
        return 'Not configured', 503      # Meta retries later, once the secret is saved
    if not security.verify_signature(raw, request.headers.get('X-Hub-Signature-256', ''), secret):
        core.record_error('webhook', message='Invalid X-Hub-Signature-256; event rejected.', commit=True)
        return 'Invalid signature', 401

    now = datetime.utcnow()
    settings.last_webhook_at = now
    try:
        payload = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        core.record_error('webhook', message='Malformed JSON in a signed webhook request.')
        core.commit_with_retry()
        return 'Bad JSON', 400

    event, duplicate = webhook_svc.register_event(raw, signature_ok=True)
    if duplicate:
        core.commit_with_retry()
        return 'OK', 200
    try:
        automation_events = webhook_svc.process(payload, event, settings)
        event.processed_ok = True
        settings.last_webhook_ok_at = now
        core.commit_with_retry()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('WhatsApp webhook processing failed')
        # Store a sanitized failure; return 500 so Meta retries the delivery.
        try:
            ev, _ = webhook_svc.register_event(raw + b'#failed', signature_ok=True)
            ev.error = security.redact(str(e))[:300]
            core.record_error('webhook', message='Processing failed: ' + security.redact(str(e))[:400])
            core.commit_with_retry()
        except Exception:
            db.session.rollback()
        return 'Error', 500

    if automation_events:
        # Run automations off the request thread so Meta gets its 200 at once.
        from app.whatsapp.services import automations
        if current_app.config.get('WHATSAPP_SYNC_AUTOMATIONS'):   # tests
            automations.run_events(current_app._get_current_object(), automation_events)
        else:
            threading.Thread(target=automations.run_events, daemon=True,
                             args=(current_app._get_current_object(), automation_events)).start()
    return 'OK', 200
