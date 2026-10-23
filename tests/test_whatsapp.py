"""Tests for the WhatsApp module.

Uses a throw-away SQLite file and a fake Meta Graph API (nothing is sent to
Meta or to any customer):

    venv\\Scripts\\python.exe -m unittest tests.test_whatsapp -v
"""
import hashlib
import hmac
import io
import json
import os
import re
import shutil
import tempfile
import time
import unittest
import urllib.error
from datetime import datetime, timedelta
from unittest import mock

for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS', 'WHATSAPP'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from config import Config  # noqa: E402

_TMP = tempfile.mkdtemp(prefix='whatsapp_test_')

APP_SECRET = 'test-app-secret-123'
TOKEN = 'EAAGtesttokenabcdefghijklmnop1234'
VERIFY = 'verify-me-please'
PNID = '1111111111'
WABA = '2222222222'


class _TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')
    SERVER_NAME = 'crm.test'
    WHATSAPP_SYNC_AUTOMATIONS = True


from app import create_app, db  # noqa: E402
from app.models import Customer, Sale, Task, User  # noqa: E402
from app.whatsapp.models import (WhatsAppAutomation, WhatsAppAutomationLog, WhatsAppCampaign,  # noqa: E402
                                 WhatsAppCampaignRecipient, WhatsAppContact, WhatsAppConversation, WhatsAppMessage,
                                 WhatsAppSettings, WhatsAppStatusEvent, WhatsAppTemplate, WhatsAppUserPermission,
                                 WhatsAppWebhookEvent)
from app.whatsapp.services import cloud_api, security  # noqa: E402

_REAL_REQUEST = cloud_api.CloudAPI.request


class FakeGraph:
    """Stands in for CloudAPI.request and records every call."""
    calls = []
    fail = None          # ApiError to raise for sends
    counter = 0

    @classmethod
    def reset(cls):
        cls.calls, cls.fail, cls.counter = [], None, 0

    @staticmethod
    def patched(api_self, *args, **kwargs):
        return FakeGraph.request(*args, **kwargs)

    @classmethod
    def request(cls, method, path, params=None, body=None, data=None, content_type=None, is_send=False):
        cls.calls.append((method, path, body))
        if path.endswith('/messages') and method == 'POST':
            if body.get('status') == 'read':
                return {'success': True}
            if cls.fail:
                raise cls.fail
            cls.counter += 1
            return {'messaging_product': 'whatsapp', 'messages': [{'id': f'wamid.OUT{cls.counter}'}]}
        if path.endswith('/media') and method == 'POST':
            return {'id': 'media-123'}
        if path == PNID:
            if cls.fail:
                raise cls.fail
            return {'display_phone_number': '+92 300 0000000', 'verified_name': 'Test Co', 'quality_rating': 'GREEN'}
        if path.endswith('/subscribed_apps'):
            return {'data': [{'whatsapp_business_api_data': {'name': 'CRM'}}]}
        if path.endswith('/message_templates') and method == 'GET':
            return {'data': [
                {'id': 't1', 'name': 'invoice_ready', 'language': 'en', 'status': 'APPROVED', 'category': 'UTILITY',
                 'components': [{'type': 'BODY', 'text': 'Hi {{1}}, invoice {{2}} is ready.'}]},
                {'id': 't2', 'name': 'promo', 'language': 'en', 'status': 'PENDING', 'category': 'MARKETING',
                 'components': [{'type': 'BODY', 'text': 'Sale now'}]},
            ]}
        if path == WABA:
            return {'id': WABA, 'name': 'Test WABA'}
        return {}


class WhatsAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(_TestConfig)
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
        cls.patcher = mock.patch.object(cloud_api.CloudAPI, 'request', FakeGraph.patched)
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        shutil.rmtree(_TMP, ignore_errors=True)

    def setUp(self):
        FakeGraph.reset()
        os.environ.pop('WHATSAPP_ENCRYPTION_KEY', None)
        with self.app.app_context():
            with db.engine.connect() as conn:
                conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
                for (name,) in conn.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                    conn.exec_driver_sql(f'DELETE FROM "{name}"')
                conn.commit()
            for name, role in (('admin', 'admin'), ('staff', 'user'), ('other', 'user')):
                u = User(username=name, email=f'{name}@example.com', role=role)
                u.set_password('realpass1')
                db.session.add(u)
            db.session.add(WhatsAppSettings(
                phone_number_id=PNID, waba_id=WABA, graph_version='v23.0',
                access_token_enc=security.encrypt(TOKEN), app_secret_enc=security.encrypt(APP_SECRET),
                verify_token_enc=security.encrypt(VERIFY), connection_status='connected', campaigns_enabled=True))
            db.session.commit()
            self.ids = {u.username: u.id for u in User.query.all()}
        self.client = self.app.test_client()

    # ── helpers ────────────────────────────────────────────────────────
    def login(self, username):
        html = self.client.get('/auth/login').get_data(as_text=True)
        token = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html).group(1)
        r = self.client.post('/auth/login', data={'csrf_token': token, 'username': username, 'password': 'realpass1'})
        self.assertEqual(r.status_code, 302)

    def wa_csrf(self):
        html = self.client.get('/whatsapp/inbox').get_data(as_text=True)
        return re.search(r'window\.WA_CSRF = "([^"]+)"', html).group(1)

    def post_json(self, url, data, csrf=None):
        return self.client.post(url, json=data, headers={'X-CSRFToken': csrf or self.wa_csrf()})

    def webhook(self, payload, secret=APP_SECRET, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode()
        sig = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return self.client.post('/webhooks/whatsapp', data=body, content_type='application/json',
                                headers={'X-Hub-Signature-256': sig})

    @staticmethod
    def inbound(wamid='wamid.IN1', text='Hello', sender='923001234567', ts=None, name='Ali Khan'):
        return {'object': 'whatsapp_business_account', 'entry': [{'id': WABA, 'changes': [{
            'field': 'messages', 'value': {
                'messaging_product': 'whatsapp', 'metadata': {'display_phone_number': '923000000000',
                                                              'phone_number_id': PNID},
                'contacts': [{'profile': {'name': name}, 'wa_id': sender}],
                'messages': [{'from': sender, 'id': wamid, 'timestamp': str(int(ts or time.time())),
                              'type': 'text', 'text': {'body': text}}]}}]}]}

    @staticmethod
    def status(wamid, status, ts=None, errors=None):
        s = {'id': wamid, 'status': status, 'timestamp': str(int(ts or time.time())), 'recipient_id': '923001234567'}
        if errors:
            s['errors'] = errors
        return {'object': 'whatsapp_business_account', 'entry': [{'id': WABA, 'changes': [{
            'field': 'messages', 'value': {'messaging_product': 'whatsapp',
                                           'metadata': {'phone_number_id': PNID}, 'statuses': [s]}}]}]}

    def conv(self):
        with self.app.app_context():
            return WhatsAppConversation.query.first().id

    def sync_templates(self):
        self.login('admin')
        r = self.client.post('/whatsapp/templates/sync', data={'csrf_token': self.wa_csrf()})
        self.assertEqual(r.status_code, 302)

    # ── 1-3: existing CRM keeps working ────────────────────────────────
    def test_existing_crm_pages_and_login(self):
        self.login('admin')
        for url in ('/', '/sales/customers', '/users/list', '/auth/logout'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302 if url == '/auth/logout' else 200, url)
        with self.app.app_context():
            c = Customer(name='Cust A', phone='0300 1234567')
            db.session.add(c)
            db.session.commit()
            s = Sale(invoice_number='INV-1', customer_id=c.id, total=100, status='unpaid')
            db.session.add(s)
            db.session.commit()
            cid, sid = c.id, s.id
        self.login('admin')
        r = self.client.get(f'/sales/customer/{cid}')
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'/whatsapp/customer/{cid}', r.get_data(as_text=True))
        r = self.client.get(f'/sales/invoice/{sid}')
        self.assertIn(r.status_code, (200, 302))

    # ── 4: navigation and permissions ──────────────────────────────────
    def test_sidebar_and_permissions(self):
        self.login('admin')
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('/whatsapp/inbox', html)
        for url in ('/whatsapp/', '/whatsapp/inbox', '/whatsapp/contacts', '/whatsapp/templates',
                    '/whatsapp/campaigns', '/whatsapp/campaigns/new', '/whatsapp/automations',
                    '/whatsapp/automations/new', '/whatsapp/reports', '/whatsapp/contacts/new',
                    '/whatsapp/contacts/import', '/whatsapp/contacts/duplicates', '/whatsapp/templates/new',
                    '/whatsapp/reports?range=today', '/whatsapp/reports?range=custom&start=2026-01-01&end=2026-02-01',
                    '/whatsapp/?range=30d') + tuple(f'/whatsapp/settings?tab={t}' for t in (
                        'connection', 'webhook', 'messaging', 'media', 'staff', 'notifications', 'diagnostics')):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
        self.client.get('/auth/logout')

        self.login('staff')
        self.assertNotIn('/whatsapp/inbox', self.client.get('/').get_data(as_text=True))
        self.assertEqual(self.client.get('/whatsapp/').status_code, 302)
        self.assertEqual(self.client.get('/whatsapp/api/conversations').status_code, 403)
        self.assertEqual(self.client.get('/whatsapp/settings').status_code, 302)

    def test_assigned_only_access(self):
        self.webhook(self.inbound())
        with self.app.app_context():
            db.session.add(WhatsAppUserPermission(user_id=self.ids['staff'], can_view=True, can_reply=True))
            db.session.commit()
        cid = self.conv()
        self.login('staff')
        self.assertEqual(self.client.get('/whatsapp/api/conversations').get_json()['items'], [])
        self.assertEqual(self.client.get(f'/whatsapp/api/conversations/{cid}').status_code, 403)
        self.assertEqual(self.client.get('/whatsapp/settings').status_code, 302)
        with self.app.app_context():
            db.session.get(WhatsAppConversation, cid).assigned_to_id = self.ids['staff']
            db.session.commit()
        self.assertEqual(len(self.client.get('/whatsapp/api/conversations').get_json()['items']), 1)
        self.assertEqual(self.client.get(f'/whatsapp/api/conversations/{cid}').status_code, 200)
        # can't assign without can_assign
        r = self.post_json(f'/whatsapp/api/conversations/{cid}/update', {'assigned_to_id': self.ids['other']})
        self.assertEqual(r.status_code, 403)

    def test_admin_assigns_and_permission_change_audited(self):
        self.webhook(self.inbound())
        cid = self.conv()
        self.login('admin')
        r = self.post_json(f'/whatsapp/api/conversations/{cid}/update', {'assigned_to_id': self.ids['staff']})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['conversation']['assigned_to'], 'staff')
        r = self.client.post('/whatsapp/settings/permissions', data={
            'csrf_token': self.wa_csrf(), f'p_{self.ids["staff"]}_can_view': '1'})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            self.assertTrue(WhatsAppUserPermission.query.filter_by(user_id=self.ids['staff']).first().can_view)
        html = self.client.get('/whatsapp/settings?tab=diagnostics').get_data(as_text=True)
        self.assertIn('permissions.change', html)
        self.assertIn('conversation.update', html)

    def test_csrf_required(self):
        self.login('admin')
        r = self.client.post('/whatsapp/settings/connection', data={'phone_number_id': '1'})
        self.assertEqual(r.status_code, 302)                              # page: flash + back
        with self.app.app_context():
            self.assertEqual(WhatsAppSettings.query.first().phone_number_id, PNID)   # nothing saved
        r = self.client.post('/whatsapp/api/conversations/1/send', json={'text': 'x'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('session expired', r.get_json()['error'])

    # ── 5-7: settings, masking, connection test ────────────────────────
    def test_settings_masking_and_blank_preserves(self):
        self.login('admin')
        html = self.client.get('/whatsapp/settings').get_data(as_text=True)
        self.assertNotIn(TOKEN, html)
        self.assertNotIn(APP_SECRET, html)
        self.assertNotIn(VERIFY, html)
        r = self.client.post('/whatsapp/settings/connection', data={
            'csrf_token': self.wa_csrf(), 'phone_number_id': PNID, 'waba_id': WABA, 'graph_version': 'v23.0',
            'access_token': '', 'app_secret': '', 'verify_token': '', 'default_country_code': '92'})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            s = WhatsAppSettings.query.first()
            self.assertEqual(security.decrypt(s.access_token_enc), TOKEN)
            self.assertEqual(security.decrypt(s.app_secret_enc), APP_SECRET)
            self.assertEqual(s.connection_status, 'unknown')   # must be re-tested after a save
        r = self.client.post('/whatsapp/settings/connection', data={
            'csrf_token': self.wa_csrf(), 'phone_number_id': 'abc', 'graph_version': 'v23.0'}, follow_redirects=True)
        self.assertIn('digits only', r.get_data(as_text=True))

    def test_encryption_at_rest(self):
        from cryptography.fernet import Fernet
        os.environ['WHATSAPP_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
        try:
            self.login('admin')
            self.client.post('/whatsapp/settings/connection', data={
                'csrf_token': self.wa_csrf(), 'phone_number_id': PNID, 'graph_version': 'v23.0',
                'access_token': 'EAAGnewtoken99999999999'})
            with self.app.app_context():
                stored = WhatsAppSettings.query.first().access_token_enc
                self.assertTrue(stored.startswith('fernet:'))
                self.assertNotIn('EAAGnewtoken', stored)
                self.assertEqual(security.decrypt(stored), 'EAAGnewtoken99999999999')
        finally:
            os.environ.pop('WHATSAPP_ENCRYPTION_KEY', None)

    def test_connection_test_success_and_failure(self):
        self.login('admin')
        r = self.client.post('/whatsapp/settings/test', data={'csrf_token': self.wa_csrf()}, follow_redirects=True)
        html = r.get_data(as_text=True)
        self.assertIn('Connected', html)
        self.assertIn('Test Co', html)
        FakeGraph.fail = cloud_api.ApiError('Error validating access token', code=190, kind='invalid_token')
        r = self.client.post('/whatsapp/settings/test', data={'csrf_token': self.wa_csrf()}, follow_redirects=True)
        html = r.get_data(as_text=True)
        self.assertIn('Invalid token', html)
        self.assertNotIn(TOKEN, html)
        with self.app.app_context():
            self.assertEqual(WhatsAppSettings.query.first().connection_status, 'error')

    def test_http_error_classification_and_redaction(self):
        api = cloud_api.CloudAPI(cloud_api.Credentials(PNID, WABA, TOKEN))
        body = json.dumps({'error': {'message': f'Bad token {TOKEN}', 'code': 190}}).encode()
        err = urllib.error.HTTPError('u', 401, 'x', {}, io.BytesIO(body))
        with mock.patch.object(cloud_api.CloudAPI, 'request', _REAL_REQUEST), \
                mock.patch.object(cloud_api.CloudAPI, '_open', side_effect=err):
            with self.assertRaises(cloud_api.ApiError) as ctx:
                api.get_phone_number()
        self.assertEqual(ctx.exception.kind, 'invalid_token')
        self.assertNotIn(TOKEN, ctx.exception.message)
        with mock.patch.object(cloud_api.CloudAPI, 'request', _REAL_REQUEST), \
                mock.patch.object(cloud_api.CloudAPI, '_open', side_effect=urllib.error.URLError('timed out')):
            with self.assertRaises(cloud_api.ApiError) as ctx:
                api.send_message('92300', 'text', {'body': 'x'})
        self.assertEqual(ctx.exception.kind, 'network')
        self.assertTrue(ctx.exception.uncertain)

    # ── 8-11: webhook ──────────────────────────────────────────────────
    def test_webhook_verification(self):
        ok = self.client.get(f'/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token={VERIFY}&hub.challenge=12345')
        self.assertEqual((ok.status_code, ok.get_data(as_text=True)), (200, '12345'))
        bad = self.client.get('/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=12345')
        self.assertEqual(bad.status_code, 403)
        self.assertEqual(self.client.get('/webhooks/whatsapp').status_code, 403)

    def test_webhook_rejects_bad_signature_and_bad_json(self):
        r = self.webhook(self.inbound(), secret='wrong-secret')
        self.assertEqual(r.status_code, 401)
        r = self.client.post('/webhooks/whatsapp', data=b'{}', content_type='application/json')
        self.assertEqual(r.status_code, 401)
        r = self.webhook(None, raw=b'{not json')
        self.assertEqual(r.status_code, 400)
        with self.app.app_context():
            self.assertEqual(WhatsAppMessage.query.count(), 0)

    def test_incoming_message_and_duplicates(self):
        payload = self.inbound(text='Hi there')
        self.assertEqual(self.webhook(payload).status_code, 200)
        self.assertEqual(self.webhook(payload).status_code, 200)          # Meta retry, same body
        payload2 = self.inbound(text='Hi there')                           # same wamid, new body
        payload2['entry'][0]['id'] = 'WABA1 '
        self.assertEqual(self.webhook(payload2).status_code, 200)
        with self.app.app_context():
            self.assertEqual(WhatsAppMessage.query.count(), 1)
            self.assertEqual(WhatsAppContact.query.count(), 1)
            c = WhatsAppContact.query.first()
            self.assertEqual((c.wa_id, c.profile_name), ('923001234567', 'Ali Khan'))
            conv = WhatsAppConversation.query.first()
            self.assertEqual(conv.unread_count, 1)
            self.assertTrue(conv.window_open)
            self.assertEqual(conv.last_message_preview, 'Hi there')
            self.assertEqual(WhatsAppWebhookEvent.query.count(), 2)
        self.login('admin')
        items = self.client.get('/whatsapp/api/conversations?filter=unread').get_json()['items']
        self.assertEqual(len(items), 1)
        msgs = self.client.get(f'/whatsapp/api/conversations/{items[0]["id"]}/messages').get_json()['items']
        self.assertEqual(msgs[0]['body'], 'Hi there')
        with self.app.app_context():
            self.assertEqual(WhatsAppConversation.query.first().unread_count, 0)   # opened -> read
        self.assertTrue(any(c[2] and c[2].get('status') == 'read' for c in FakeGraph.calls))

    def test_other_phone_number_ignored(self):
        p = self.inbound()
        p['entry'][0]['changes'][0]['value']['metadata']['phone_number_id'] = '999'
        self.assertEqual(self.webhook(p).status_code, 200)
        with self.app.app_context():
            self.assertEqual(WhatsAppMessage.query.count(), 0)

    # ── 12-13: sending and statuses ────────────────────────────────────
    def test_send_text_and_status_updates(self):
        self.webhook(self.inbound())
        cid = self.conv()
        self.login('admin')
        r = self.post_json(f'/whatsapp/api/conversations/{cid}/send', {'text': 'Thanks!'})
        self.assertEqual(r.status_code, 200, r.get_json())
        m = r.get_json()['message']
        self.assertEqual((m['status'], m['wamid']), ('accepted', 'wamid.OUT1'))
        sent = [c for c in FakeGraph.calls if c[2] and c[2].get('type') == 'text']
        self.assertEqual(sent[0][2]['to'], '923001234567')

        now = time.time()
        for st, off in (('sent', 1), ('delivered', 2), ('read', 3)):
            self.assertEqual(self.webhook(self.status('wamid.OUT1', st, now + off)).status_code, 200)
        self.webhook(self.status('wamid.OUT1', 'delivered', now + 2))     # duplicate status
        self.webhook(self.status('wamid.OUT1', 'sent', now + 5))          # late, out of order
        with self.app.app_context():
            msg = WhatsAppMessage.query.filter_by(wamid='wamid.OUT1').one()
            self.assertEqual(msg.status, 'read')
            self.assertEqual(WhatsAppMessage.query.count(), 2)           # no message per status
            self.assertEqual(WhatsAppStatusEvent.query.count(), 4)

    def test_send_failure_and_timeout(self):
        self.webhook(self.inbound())
        cid = self.conv()
        self.login('admin')
        FakeGraph.fail = cloud_api.ApiError('Recipient not in allowed list', code=131030, kind='recipient_not_allowed')
        r = self.post_json(f'/whatsapp/api/conversations/{cid}/send', {'text': 'Hi'})
        self.assertEqual(r.status_code, 502)
        failed = r.get_json()['message']
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['error']['code'], '131030')
        FakeGraph.fail = cloud_api.ApiError('timed out', kind='network', retryable=True, uncertain=True)
        r = self.post_json(f'/whatsapp/api/conversations/{cid}/send', {'text': 'Hi again'})
        unknown = r.get_json()['message']
        self.assertEqual(unknown['status'], 'unknown')
        FakeGraph.fail = None
        # retrying an "unknown" message needs explicit confirmation
        r = self.post_json(f'/whatsapp/api/messages/{unknown["id"]}/retry', {})
        self.assertEqual(r.status_code, 409)
        r = self.post_json(f'/whatsapp/api/messages/{failed["id"]}/retry', {})
        self.assertEqual(r.status_code, 200)
        r = self.post_json(f'/whatsapp/api/messages/{failed["id"]}/retry', {})
        self.assertEqual(r.status_code, 400)                              # already retried

    def test_failed_status_webhook(self):
        self.webhook(self.inbound())
        cid = self.conv()
        self.login('admin')
        self.post_json(f'/whatsapp/api/conversations/{cid}/send', {'text': 'Hi'})
        self.webhook(self.status('wamid.OUT1', 'failed', errors=[{'code': 131026, 'title': 'Message undeliverable',
                                                                  'error_data': {'details': 'not on WhatsApp'}}]))
        with self.app.app_context():
            msg = WhatsAppMessage.query.filter_by(wamid='wamid.OUT1').one()
            self.assertEqual((msg.status, msg.error_code, msg.error_detail),
                             ('failed', '131026', 'not on WhatsApp'))

    # ── 14-15: templates and the 24h window ────────────────────────────
    def test_closed_window_requires_template(self):
        self.webhook(self.inbound(ts=time.time() - 25 * 3600))
        cid = self.conv()
        self.sync_templates()
        r = self.post_json(f'/whatsapp/api/conversations/{cid}/send', {'text': 'Hi'})
        self.assertEqual((r.status_code, r.get_json()['code']), (400, 'window_closed'))
        with self.app.app_context():
            approved = WhatsAppTemplate.query.filter_by(name='invoice_ready').one().id
            pending = WhatsAppTemplate.query.filter_by(name='promo').one().id
        r = self.post_json(f'/whatsapp/api/conversations/{cid}/send-template',
                           {'template_id': pending, 'values': {}})
        self.assertEqual(r.get_json()['code'], 'not_approved')
        r = self.post_json(f'/whatsapp/api/conversations/{cid}/send-template',
                           {'template_id': approved, 'values': {'body.1': 'Ali'}})
        self.assertIn('Fill in', r.get_json()['error'])
        r = self.post_json(f'/whatsapp/api/conversations/{cid}/send-template',
                           {'template_id': approved, 'values': {'body.1': 'Ali', 'body.2': 'INV-9'}})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = [c[2] for c in FakeGraph.calls if c[2] and c[2].get('type') == 'template'][-1]
        self.assertEqual(body['template']['name'], 'invoice_ready')
        self.assertEqual([p['text'] for p in body['template']['components'][0]['parameters']], ['Ali', 'INV-9'])
        self.assertIn('invoice INV-9 is ready', r.get_json()['message']['body'])

    def test_template_status_webhook(self):
        self.sync_templates()
        self.webhook({'object': 'whatsapp_business_account', 'entry': [{'id': WABA, 'changes': [{
            'field': 'message_template_status_update',
            'value': {'event': 'REJECTED', 'message_template_name': 'invoice_ready',
                      'message_template_language': 'en', 'reason': 'INVALID_FORMAT'}}]}]})
        with self.app.app_context():
            t = WhatsAppTemplate.query.filter_by(name='invoice_ready').one()
            self.assertEqual((t.status, t.is_approved, t.rejected_reason), ('REJECTED', False, 'INVALID_FORMAT'))

    # ── 16-17: contacts, duplicates and opt-out ────────────────────────
    def test_contacts_create_and_duplicates(self):
        self.login('admin')
        r = self.client.post('/whatsapp/contacts/new', data={'csrf_token': self.wa_csrf(), 'name': 'Sara',
                                                             'phone': '0300 7654321', 'consent_status': 'opted_in',
                                                             'consent_source': 'Form'})
        self.assertEqual(r.status_code, 302)
        r = self.client.post('/whatsapp/contacts/new', data={'csrf_token': self.wa_csrf(), 'name': 'Sara 2',
                                                             'phone': '+92 300-7654321'})
        self.assertIn('already exists', r.get_data(as_text=True))
        with self.app.app_context():
            c = WhatsAppContact.query.one()
            self.assertEqual((c.wa_id, c.consent_status), ('923007654321', 'opted_in'))
            self.assertIsNotNone(c.consent_at)
            db.session.add(WhatsAppContact(wa_id='13007654321', name='Sara wrong cc'))
            db.session.commit()
        html = self.client.get('/whatsapp/contacts/duplicates').get_data(as_text=True)
        self.assertIn('Sara wrong cc', html)

    def test_csv_import_preview_and_export(self):
        self.login('admin')
        csv_bytes = (b'name,phone,consent_status,consent_source,tags\nA,03001111111,opted_in,Shop,vip\n'
                     b'B,notaphone,unknown,,\nC,03001111111,unknown,,\nD,03002222222,opted_in,,\n')
        r = self.client.post('/whatsapp/contacts/import', data={
            'csrf_token': self.wa_csrf(), 'file': (io.BytesIO(csv_bytes), 'c.csv')}, content_type='multipart/form-data')
        html = r.get_data(as_text=True)
        self.assertIn('Duplicate of an earlier row', html)
        self.assertIn('need a consent_source', html)
        with self.app.app_context():
            self.assertEqual(WhatsAppContact.query.count(), 0)             # preview saves nothing
        token = re.search(r'name="token" value="([0-9a-f]+)"', html).group(1)
        self.client.post('/whatsapp/contacts/import/confirm', data={'csrf_token': self.wa_csrf(), 'token': token})
        with self.app.app_context():
            self.assertEqual(WhatsAppContact.query.count(), 1)
            self.assertEqual(WhatsAppContact.query.one().tag_list, ['vip'])
        r = self.client.get('/whatsapp/contacts/export')
        self.assertIn('+923001111111', r.get_data(as_text=True))

    def test_opt_out_keyword_blocks_templates(self):
        self.webhook(self.inbound())
        self.webhook(self.inbound(wamid='wamid.IN2', text='stop'))
        with self.app.app_context():
            c = WhatsAppContact.query.one()
            self.assertEqual(c.consent_status, 'opted_out')
            self.assertIsNotNone(c.opted_out_at)
        self.sync_templates()
        with self.app.app_context():
            tid = WhatsAppTemplate.query.filter_by(name='invoice_ready').one().id
        r = self.post_json(f'/whatsapp/api/conversations/{self.conv()}/send-template',
                           {'template_id': tid, 'values': {'body.1': 'a', 'body.2': 'b'}})
        self.assertEqual(r.get_json()['code'], 'opted_out')

    # ── 18: campaigns ──────────────────────────────────────────────────
    def test_campaign_flow_and_dedupe(self):
        self.sync_templates()
        with self.app.app_context():
            tid = WhatsAppTemplate.query.filter_by(name='invoice_ready').one().id
            for i, consent in enumerate(('opted_in', 'opted_in', 'unknown', 'opted_out')):
                c = WhatsAppContact(wa_id=f'92300000000{i}', name=f'C{i}', consent_status=consent)
                c.set_tags(['vip'])
                db.session.add(c)
            db.session.commit()
        r = self.client.post('/whatsapp/campaigns/new', data={
            'csrf_token': self.wa_csrf(), 'name': 'Promo', 'tag_filter': 'vip', 'template_id': tid,
            'var_body.1': '{contact_name}', 'var_body.2': 'X'})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            camp = WhatsAppCampaign.query.one()
            self.assertEqual(camp.recipients.count(), 2)                   # only opted in
            cid = camp.id
        self.assertIn('Hi C0, invoice X is ready', self.client.get(f'/whatsapp/campaigns/{cid}').get_data(as_text=True))
        r = self.client.post(f'/whatsapp/campaigns/{cid}/confirm', data={'csrf_token': self.wa_csrf(),
                                                                          'confirm_count': '5'})
        with self.app.app_context():
            self.assertEqual(db.session.get(WhatsAppCampaign, cid).status, 'draft')   # wrong count
        self.client.post(f'/whatsapp/campaigns/{cid}/confirm', data={'csrf_token': self.wa_csrf(),
                                                                      'confirm_count': '2'})
        from app.whatsapp.services import campaigns
        with self.app.app_context():
            # an opt-out after confirming is respected at send time
            c1 = WhatsAppContact.query.filter_by(wa_id='923000000001').one()
            c1.consent_status = 'opted_out'
            db.session.commit()
            self.assertEqual(campaigns.tick(), 2)
            self.assertEqual(campaigns.tick(), 0)                          # nothing sent twice
            camp = db.session.get(WhatsAppCampaign, cid)
            self.assertEqual(camp.status, 'completed')
            k = campaigns.counts(camp)
            self.assertEqual((k['accepted'], k['skipped']), (1, 1))
        sends = [c for c in FakeGraph.calls if c[2] and c[2].get('type') == 'template']
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0][2]['template']['components'][0]['parameters'][0]['text'], 'C0')

    def test_campaign_schedule_and_cancel(self):
        self.sync_templates()
        with self.app.app_context():
            tid = WhatsAppTemplate.query.filter_by(name='invoice_ready').one().id
            db.session.add(WhatsAppContact(wa_id='923000000009', name='Z', consent_status='opted_in'))
            db.session.commit()
        self.client.post('/whatsapp/campaigns/new', data={'csrf_token': self.wa_csrf(), 'name': 'Later',
                                                          'template_id': tid, 'var_body.1': 'a', 'var_body.2': 'b'})
        with self.app.app_context():
            cid = WhatsAppCampaign.query.one().id
        self.client.post(f'/whatsapp/campaigns/{cid}/confirm', data={
            'csrf_token': self.wa_csrf(), 'confirm_count': '1', 'scheduled_at': '2099-01-01T10:00'})
        from app.whatsapp.services import campaigns
        with self.app.app_context():
            self.assertEqual(db.session.get(WhatsAppCampaign, cid).status, 'scheduled')
            self.assertEqual(campaigns.tick(), 0)
        self.client.post(f'/whatsapp/campaigns/{cid}/cancel', data={'csrf_token': self.wa_csrf()})
        with self.app.app_context():
            self.assertEqual(db.session.get(WhatsAppCampaign, cid).status, 'cancelled')
            self.assertEqual(WhatsAppCampaignRecipient.query.one().status, 'skipped')

    # ── automations ────────────────────────────────────────────────────
    def test_automation_dry_run_then_live(self):
        self.login('admin')
        r = self.client.post('/whatsapp/automations/new', data={
            'csrf_token': self.wa_csrf(), 'name': 'Tag pricing', 'trigger': 'inbound_message', 'action': 'add_tag',
            'cond_keyword': 'price', 'cfg_tag': 'lead'})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            a = WhatsAppAutomation.query.one()
            self.assertEqual((a.is_enabled, a.dry_run), (False, True))
            a.is_enabled = True
            db.session.commit()
        self.webhook(self.inbound(wamid='wamid.A1', text='what is the price?'))
        self.webhook(self.inbound(wamid='wamid.A2', text='hello'))
        with self.app.app_context():
            results = sorted(l.result for l in WhatsAppAutomationLog.query.all())
            self.assertEqual(results, ['dry_run', 'skipped'])
            self.assertEqual(WhatsAppContact.query.one().tag_list, [])
            WhatsAppAutomation.query.one().dry_run = False
            db.session.commit()
        self.webhook(self.inbound(wamid='wamid.A3', text='PRICE list please'))
        with self.app.app_context():
            self.assertEqual(WhatsAppContact.query.one().tag_list, ['lead'])
            self.assertEqual(WhatsAppAutomationLog.query.filter_by(result='done').count(), 1)

    def test_automation_create_task_and_invoice_trigger(self):
        with self.app.app_context():
            cust = Customer(name='Inv Cust')
            db.session.add(cust)
            db.session.commit()
            db.session.add(WhatsAppContact(wa_id='923005555555', customer_id=cust.id, consent_status='opted_in'))
            a = WhatsAppAutomation(name='Task on invoice', trigger='invoice_created', action='create_task',
                                   action_config_json=json.dumps({'title': 'Call {contact_name} re {invoice_number}',
                                                                  'priority': 'High', 'due_days': 1}),
                                   is_enabled=True, dry_run=False, created_by=self.ids['admin'],
                                   created_at=datetime.utcnow() - timedelta(minutes=5))
            db.session.add(a)
            db.session.add(Sale(invoice_number='INV-OLD', customer_id=cust.id, total=10,
                                created_at=datetime.utcnow() - timedelta(days=3)))
            db.session.add(Sale(invoice_number='INV-NEW', customer_id=cust.id, total=50))
            db.session.commit()
            from app.whatsapp.services import automations
            automations.scan_crm_events()
            automations.scan_crm_events()                                   # no duplicate actions
            tasks = Task.query.all()
            self.assertEqual(len(tasks), 1)
            self.assertIn('INV-NEW', tasks[0].title)

    # ── media ──────────────────────────────────────────────────────────
    def test_media_validation(self):
        from app.whatsapp.services import messaging
        png = b'\x89PNG\r\n\x1a\n' + b'0' * 100
        self.assertEqual(messaging.validate_upload(png, 'a.png', 16), ('image', 'image/png'))
        with self.assertRaises(messaging.SendError):
            messaging.validate_upload(b'MZ\x90\x00' + b'0' * 50, 'evil.pdf', 16)      # exe renamed
        with self.assertRaises(messaging.SendError):
            messaging.validate_upload(b'\xff\xd8\xff' + b'0' * (6 * 1024 * 1024), 'big.jpg', 16)

        self.webhook(self.inbound())
        self.login('admin')
        r = self.client.post(f'/whatsapp/api/conversations/{self.conv()}/send-media',
                             data={'file': (io.BytesIO(png), 'pic.png'), 'caption': 'Look'},
                             headers={'X-CSRFToken': self.wa_csrf()}, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 200, r.get_json())
        m = r.get_json()['message']
        self.assertEqual((m['type'], m['body']), ('image', 'Look'))
        self.assertEqual(self.client.get(m['media']['url']).data, png)
        self.client.get('/auth/logout')
        self.login('staff')
        self.assertIn(self.client.get(m['media']['url']).status_code, (302, 403))

    def test_phone_normalization(self):
        from app.whatsapp.services import phone
        for raw in ('+92 300 1234567', '0092-300-1234567', '03001234567', '923001234567'):
            self.assertEqual(phone.normalize('+' + raw if raw.startswith('92') else raw), '923001234567')
        for bad in ('', 'abc', '12', '0'):
            with self.assertRaises(phone.InvalidPhone):
                phone.normalize(bad)


if __name__ == '__main__':
    unittest.main()
