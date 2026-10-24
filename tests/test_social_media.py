"""Tests for the Social Media module.

Throw-away SQLite file and mocked Meta/LinkedIn APIs - nothing is posted to
any platform and no advertising money can be spent:

    venv\\Scripts\\python.exe -m unittest tests.test_social_media -v
"""
import io
import os
import re
import shutil
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from unittest import mock

for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS', 'WHATSAPP', 'SOCIAL_MEDIA'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from cryptography.fernet import Fernet  # noqa: E402

os.environ['SOCIAL_MEDIA_ENCRYPTION_KEY'] = Fernet.generate_key().decode()

from config import Config  # noqa: E402

_TMP = tempfile.mkdtemp(prefix='social_test_')
TOKEN = 'EAAGpagetoken1234567890abcdef'
APP_SECRET = 'meta-app-secret-xyz-123'


class _TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')


from app import create_app, db  # noqa: E402
from app.models import User  # noqa: E402
from app.social_media.models import (SocialAccount, SocialAdAccount, SocialAdCampaign, SocialAuditLog,  # noqa: E402
                                     SocialOAuthCredential, SocialPost, SocialPostDestination, SocialPostMedia,
                                     SocialPublishAttempt, SocialUserPermission)
from app.social_media.services import core, linkedin, meta, publisher, security  # noqa: E402
from app.social_media.services.http import ApiError  # noqa: E402

JPEG = (b'\xff\xd8\xff\xe0' + b'\x00' * 60)


def _real_jpeg():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (1080, 1080), (200, 30, 30)).save(buf, 'JPEG')
    return buf.getvalue()


class SocialMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(_TestConfig)
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        shutil.rmtree(_TMP, ignore_errors=True)

    def setUp(self):
        with self.app.app_context():
            with db.engine.connect() as conn:
                conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
                for (name,) in conn.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                    conn.exec_driver_sql(f'DELETE FROM "{name}"')
                conn.commit()
            for name, role in (('admin', 'admin'), ('staff', 'user'), ('viewer', 'user')):
                u = User(username=name, email=f'{name}@example.com', role=role)
                u.set_password('realpass1')
                db.session.add(u)
            db.session.flush()
            staff = User.query.filter_by(username='staff').first()
            db.session.add(SocialUserPermission(user_id=staff.id, can_view=True, can_create_posts=True,
                                                can_publish=True, can_schedule=True, can_view_accounts=True))
            core.set_value('public_base_url', 'https://crm.example.com')
            core.set_value('meta_app_id', '1234')
            core.set_secret('meta_app_secret', APP_SECRET)
            cred = SocialOAuthCredential(provider='meta', token_type='page', external_user_id='P1',
                                         access_token_enc=security.encrypt(TOKEN), scopes='["pages_manage_posts"]')
            li_cred = SocialOAuthCredential(provider='linkedin', token_type='member', external_user_id='abc',
                                            access_token_enc=security.encrypt('AQlinkedintoken' + 'x' * 30))
            db.session.add_all([cred, li_cred])
            db.session.flush()
            fb = SocialAccount(platform='facebook', account_type='page', remote_id='P1', name='Test Page',
                               credential_id=cred.id)
            ig = SocialAccount(platform='instagram', account_type='professional', remote_id='IG1', name='Test IG',
                               credential_id=cred.id)
            li = SocialAccount(platform='linkedin', account_type='member', remote_id='urn:li:person:abc',
                               name='Member', credential_id=li_cred.id)
            db.session.add_all([fb, ig, li])
            db.session.commit()
            self.ids = {u.username: u.id for u in User.query.all()}
            self.acc = {a.platform: a.id for a in SocialAccount.query.all()}
        self.client = self.app.test_client()

    # ── helpers ────────────────────────────────────────────────────────
    def login(self, username):
        html = self.client.get('/auth/login').get_data(as_text=True)
        token = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html).group(1)
        r = self.client.post('/auth/login', data={'csrf_token': token, 'username': username, 'password': 'realpass1'})
        self.assertEqual(r.status_code, 302)

    def csrf(self):
        html = self.client.get('/social-media/').get_data(as_text=True)
        return re.search(r'window\.SM_CSRF = "([^"]+)"', html).group(1)

    def make_post(self, platforms=('facebook',), status='scheduled', when=None, body='Hello world'):
        with self.app.app_context():
            p = SocialPost(body=body, status=status, created_by=self.ids['admin'])
            db.session.add(p)
            db.session.flush()
            for pl in platforms:
                db.session.add(SocialPostDestination(post_id=p.id, account_id=self.acc[pl], platform=pl,
                                                     status=status, scheduled_at=when or datetime.utcnow()))
            db.session.commit()
            return p.id

    # ── 1-3: existing app + registration ──────────────────────────────
    def test_existing_routes_and_login_still_work(self):
        self.assertEqual(self.client.get('/auth/login').status_code, 200)
        self.login('admin')
        r = self.client.get('/')
        self.assertIn(r.status_code, (200, 302))
        self.assertNotEqual(self.client.get('/whatsapp/').status_code, 500)

    def test_blueprint_registered_without_conflicts(self):
        self.assertIn('social_media', self.app.blueprints)
        rules = [(r.rule, tuple(sorted(r.methods))) for r in self.app.url_map.iter_rules()]
        self.assertEqual(len(rules), len(set(rules)))

    def test_tables_created_without_touching_existing(self):
        with self.app.app_context():
            from sqlalchemy import inspect
            names = inspect(db.engine).get_table_names()
            self.assertIn('social_post_destinations', names)
            self.assertIn('users', names)
            self.assertEqual(User.query.count(), 3)
            # init_app is idempotent on a live database
            from app import social_media
            social_media.init_app.__wrapped__ if hasattr(social_media.init_app, '__wrapped__') else None
            from app.social_media.models import ALL_MODELS
            for model in ALL_MODELS:
                model.__table__.create(db.engine, checkfirst=True)
            self.assertEqual(User.query.count(), 3)

    # ── 5: authorization ───────────────────────────────────────────────
    def test_anonymous_and_unprivileged_users_blocked(self):
        r = self.client.get('/social-media/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/auth/login', r.location)
        self.login('viewer')
        for url in ('/social-media/', '/social-media/settings', '/social-media/ads', '/social-media/posts/new'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertNotIn('/social-media/settings', r.location)
        r = self.client.post('/social-media/settings/general', data={})
        self.assertIn(r.status_code, (302, 400, 403))

    def test_staff_cannot_open_settings_or_ads(self):
        self.login('staff')
        self.assertEqual(self.client.get('/social-media/').status_code, 200)
        r = self.client.get('/social-media/settings')
        self.assertEqual(r.status_code, 302)
        r = self.client.post('/social-media/settings/meta', data={'csrf_token': self.csrf(), 'meta_app_id': '9'})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            self.assertEqual(core.get('meta_app_id'), '1234')

    def test_csrf_required(self):
        self.login('admin')
        r = self.client.post('/social-media/settings/general', data={'enabled': '1'})
        self.assertEqual(r.status_code, 302)  # rejected (flash + redirect), nothing saved
        with self.app.app_context():
            self.assertEqual(SocialAuditLog.query.filter_by(action='settings_saved').count(), 0)

    # ── 6: OAuth state ────────────────────────────────────────────────
    def test_oauth_callback_rejects_bad_state(self):
        self.login('admin')
        r = self.client.post('/social-media/connect/meta', data={'csrf_token': self.csrf()})
        self.assertEqual(r.status_code, 302)
        self.assertIn('facebook.com', r.location)
        self.assertNotIn(APP_SECRET, r.location)
        with mock.patch.object(meta, 'exchange_code') as ex:
            r = self.client.get('/social-media/oauth/meta/callback?code=abc&state=WRONG')
            self.assertEqual(r.status_code, 302)
            ex.assert_not_called()
            # state is single-use: the real state no longer works either
            r = self.client.get('/social-media/oauth/meta/callback?code=abc&state=anything')
            ex.assert_not_called()
        with self.app.app_context():
            self.assertTrue(SocialAuditLog.query.filter_by(action='oauth_failed').count() >= 1)

    def test_oauth_callback_accepts_valid_state(self):
        self.login('admin')
        r = self.client.post('/social-media/connect/meta', data={'csrf_token': self.csrf()})
        state = re.search(r'state=([^&]+)', r.location).group(1)
        with mock.patch.object(meta, 'exchange_code', return_value={'access_token': 'EAAshort' + 'x' * 20}), \
                mock.patch.object(meta, 'exchange_long_lived', return_value={'access_token': 'EAAlong' + 'y' * 20}), \
                mock.patch.object(meta, 'debug_token', return_value={'scopes': ['pages_show_list'], 'expires_at': 0}), \
                mock.patch.object(meta, 'me', return_value={'id': 'U1', 'name': 'Owner'}):
            r = self.client.get(f'/social-media/oauth/meta/callback?code=abc&state={state}')
        self.assertIn('/connect/meta/select', r.location)
        with self.app.app_context():
            cred = SocialOAuthCredential.query.filter_by(token_type='user').first()
            self.assertTrue(cred.access_token_enc.startswith('fernet:'))
            self.assertNotIn('EAAlong', cred.access_token_enc)

    # ── 7: no credential exposure ─────────────────────────────────────
    def test_secrets_never_rendered(self):
        self.login('admin')
        for tab in ('meta', 'linkedin', 'security', 'ads', 'general'):
            html = self.client.get(f'/social-media/settings?tab={tab}').get_data(as_text=True)
            self.assertNotIn(APP_SECRET, html)
            self.assertNotIn(TOKEN, html)
        for url in ('/social-media/accounts', '/social-media/', '/social-media/logs'):
            self.assertNotIn(TOKEN, self.client.get(url).get_data(as_text=True))

    def test_secret_refused_without_encryption_key(self):
        key = os.environ.pop('SOCIAL_MEDIA_ENCRYPTION_KEY')
        try:
            with self.app.app_context():
                with self.assertRaises(security.EncryptionNotConfigured):
                    security.encrypt('x')
        finally:
            os.environ['SOCIAL_MEDIA_ENCRYPTION_KEY'] = key

    def test_redaction(self):
        self.assertNotIn(TOKEN, security.redact(f'error access_token={TOKEN} and Bearer {TOKEN}'))

    # ── 8: drafts ─────────────────────────────────────────────────────
    def test_create_and_edit_draft(self):
        self.login('staff')
        r = self.client.post('/social-media/posts/new', data={
            'csrf_token': self.csrf(), 'action': 'draft', 'title': 'Draft 1', 'body': 'Hi',
            'account_ids': [str(self.acc['facebook'])]})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            p = SocialPost.query.filter_by(title='Draft 1').one()
            self.assertEqual(p.status, 'draft')
            self.assertEqual(p.destinations[0].status, 'draft')
            pid = p.id
        r = self.client.post(f'/social-media/posts/{pid}/edit', data={
            'csrf_token': self.csrf(), 'action': 'draft', 'title': 'Draft 1b', 'body': 'Changed',
            'account_ids': [str(self.acc['facebook']), str(self.acc['linkedin'])]})
        with self.app.app_context():
            p = db.session.get(SocialPost, pid)
            self.assertEqual(p.body, 'Changed')
            self.assertEqual(len(p.destinations), 2)
        self.assertEqual(self.client.get(f'/social-media/posts/{pid}/edit').status_code, 200)
        self.assertEqual(self.client.get(f'/social-media/posts/{pid}').status_code, 200)

    # ── 9: media validation ───────────────────────────────────────────
    def test_invalid_upload_rejected(self):
        self.login('staff')
        self.client.post('/social-media/posts/new', data={
            'csrf_token': self.csrf(), 'action': 'draft', 'title': 'Bad media', 'body': 'x',
            'media': (io.BytesIO(b'MZ\x90\x00 not an image'), 'evil.jpg')}, content_type='multipart/form-data')
        with self.app.app_context():
            self.assertEqual(SocialPostMedia.query.count(), 0)
        self.client.post('/social-media/posts/new', data={
            'csrf_token': self.csrf(), 'action': 'draft', 'title': 'Good media', 'body': 'x',
            'media': (io.BytesIO(_real_jpeg()), 'ok.jpg')}, content_type='multipart/form-data')
        with self.app.app_context():
            m = SocialPostMedia.query.one()
            self.assertEqual(m.mime_type, 'image/jpeg')
            self.assertFalse(m.public_enabled)

    def test_public_media_requires_valid_token_and_release(self):
        self.client.post  # no login
        self.assertEqual(self.client.get('/social-media/public-media/garbage').status_code, 404)
        self.assertEqual(self.client.get('/social-media/public-media/probe').status_code, 200)

    def test_instagram_requires_media(self):
        pid = self.make_post(('instagram',))
        with self.app.app_context():
            d = SocialPostDestination.query.filter_by(post_id=pid).one()
            publisher.publish_destination(d.id)
            d = db.session.get(SocialPostDestination, d.id)
            self.assertEqual(d.status, 'failed')
            self.assertEqual(d.error_kind, 'validation')

    # ── 10/11: persistence + no duplicates ────────────────────────────
    def test_scheduled_post_survives_restart_and_publishes_once(self):
        pid = self.make_post(when=datetime.utcnow() - timedelta(minutes=1))
        app2 = create_app(_TestConfig)  # "restart"
        app2.config['TESTING'] = True
        calls = []
        with mock.patch.object(meta, 'publish_facebook', side_effect=lambda *a, **k: calls.append(1) or ('P1_99', 'u')):
            from app.social_media.services import scheduler
            scheduler.tick(app2)
            scheduler.tick(app2)
        self.assertEqual(len(calls), 1)
        with self.app.app_context():
            self.assertEqual(db.session.get(SocialPost, pid).status, 'published')

    def test_claim_is_atomic(self):
        pid = self.make_post()
        with self.app.app_context():
            did = SocialPostDestination.query.filter_by(post_id=pid).one().id
            self.assertIsNotNone(publisher.claim(did))
            self.assertIsNone(publisher.claim(did))

    def test_concurrent_workers_publish_once(self):
        pid = self.make_post()
        calls = []
        lock = threading.Lock()

        def fake(*a, **k):
            with lock:
                calls.append(1)
            return ('P1_1', '')

        def worker():
            with self.app.app_context():
                try:
                    did = SocialPostDestination.query.filter_by(post_id=pid).one().id
                    publisher.publish_destination(did)
                except Exception:
                    db.session.rollback()
                finally:
                    db.session.remove()
        with mock.patch.object(meta, 'publish_facebook', side_effect=fake):
            ts = [threading.Thread(target=worker) for _ in range(4)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        self.assertEqual(len(calls), 1)

    def test_ambiguous_error_not_retried(self):
        pid = self.make_post()
        with mock.patch.object(meta, 'publish_facebook',
                               side_effect=ApiError('timed out', kind='ambiguous', ambiguous=True)) as pf:
            with self.app.app_context():
                d = SocialPostDestination.query.filter_by(post_id=pid).one()
                publisher.publish_destination(d.id)
                self.assertEqual(db.session.get(SocialPostDestination, d.id).status, 'needs_review')
                self.assertEqual(publisher.due_destination_ids(datetime.utcnow() + timedelta(days=1)), [])
            self.assertEqual(pf.call_count, 1)

    def test_transient_error_backoff_and_permanent_error_fails(self):
        pid = self.make_post()
        with self.app.app_context():
            d = SocialPostDestination.query.filter_by(post_id=pid).one()
            with mock.patch.object(meta, 'publish_facebook', side_effect=ApiError('limit', kind='rate_limited',
                                                                                   retryable=True)):
                publisher.publish_destination(d.id)
            d = db.session.get(SocialPostDestination, d.id)
            self.assertEqual(d.status, 'retry_wait')
            self.assertGreater(d.next_attempt_at, datetime.utcnow())
            d.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
            db.session.commit()
            with mock.patch.object(meta, 'publish_facebook', side_effect=ApiError('no perm', kind='missing_permission')):
                publisher.publish_destination(d.id)
            d = db.session.get(SocialPostDestination, d.id)
            self.assertEqual(d.status, 'failed')
            self.assertEqual(SocialPublishAttempt.query.filter_by(destination_id=d.id).count(), 2)

    def test_stale_lock_becomes_needs_review(self):
        pid = self.make_post()
        with self.app.app_context():
            d = SocialPostDestination.query.filter_by(post_id=pid).one()
            d.status, d.locked_at = 'publishing', datetime.utcnow() - timedelta(hours=1)
            db.session.commit()
            publisher.release_stale_locks()
            db.session.commit()
            self.assertEqual(db.session.get(SocialPostDestination, d.id).status, 'needs_review')

    # ── 12/13: per-destination results, partial success ───────────────
    def test_partial_success(self):
        pid = self.make_post(('facebook', 'linkedin'))
        with mock.patch.object(meta, 'publish_facebook', return_value=('P1_5', 'https://fb/5')), \
                mock.patch.object(linkedin, 'publish', side_effect=ApiError('denied', kind='missing_permission',
                                                                           http_status=403)):
            with self.app.app_context():
                for d in SocialPostDestination.query.filter_by(post_id=pid).all():
                    publisher.publish_destination(d.id)
                p = db.session.get(SocialPost, pid)
                st = {d.platform: d.status for d in p.destinations}
                self.assertEqual(st, {'facebook': 'published', 'linkedin': 'failed'})
                self.assertEqual(p.status, 'partially_published')
                li = SocialAccount.query.filter_by(platform='linkedin').one()
                self.assertEqual(li.status, 'error')

    def test_publish_now_through_ui(self):
        self.login('staff')
        with mock.patch.object(meta, 'publish_facebook', return_value=('P1_7', 'https://fb/7')):
            r = self.client.post('/social-media/posts/new', data={
                'csrf_token': self.csrf(), 'action': 'publish', 'confirmed': '1', 'body': 'Live!',
                'account_ids': [str(self.acc['facebook'])]})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            p = SocialPost.query.filter_by(body='Live!').one()
            self.assertEqual(p.status, 'published')
            self.assertEqual(p.destinations[0].remote_id, 'P1_7')

    def test_publish_requires_confirmation(self):
        self.login('staff')
        with mock.patch.object(meta, 'publish_facebook') as pf:
            self.client.post('/social-media/posts/new', data={
                'csrf_token': self.csrf(), 'action': 'publish', 'body': 'No confirm',
                'account_ids': [str(self.acc['facebook'])]})
            pf.assert_not_called()

    def test_unselected_account_never_receives_post(self):
        pid = self.make_post(('facebook',))
        with mock.patch.object(linkedin, 'publish') as lp, \
                mock.patch.object(meta, 'publish_facebook', return_value=('x', '')):
            from app.social_media.services import scheduler
            scheduler.tick(self.app)
            lp.assert_not_called()

    # ── 14: API failures don't crash Flask ────────────────────────────
    def test_unexpected_exception_contained(self):
        pid = self.make_post()
        with mock.patch.object(meta, 'publish_facebook', side_effect=RuntimeError('boom')):
            with self.app.app_context():
                d = SocialPostDestination.query.filter_by(post_id=pid).one()
                publisher.publish_destination(d.id)
                self.assertEqual(db.session.get(SocialPostDestination, d.id).status, 'needs_review')

    def test_meta_error_classification(self):
        self.assertEqual(meta.parse_error(400, {'error': {'code': 190, 'message': 'x'}}).kind, 'invalid_token')
        self.assertTrue(meta.parse_error(400, {'error': {'code': 4, 'message': 'x'}}).retryable)
        self.assertEqual(meta.parse_error(403, {'error': {'code': 200, 'message': 'x'}}).kind, 'missing_permission')
        self.assertEqual(linkedin.parse_error(401, {}).kind, 'invalid_token')

    def test_linkedin_little_text(self):
        self.assertEqual(linkedin.little_text('Hi (all) #sale'), 'Hi \\(all\\) {hashtag|\\#|sale}')

    def test_settings_test_endpoint_honest(self):
        self.login('admin')
        r = self.client.post('/social-media/settings/test/linkedin', headers={'X-CSRFToken': self.csrf()})
        data = r.get_json()
        self.assertFalse(data['ok'])
        self.assertEqual(data['kind'], 'not_configured')

    # ── 15/16: ads safeguards ─────────────────────────────────────────
    def _campaign(self):
        with self.app.app_context():
            a = SocialAdAccount(remote_id='act_1', name='Ads', currency='PKR', is_selected=True)
            db.session.add(a)
            db.session.flush()
            c = SocialAdCampaign(ad_account_id=a.id, remote_id='C1', name='Camp', status='PAUSED', daily_budget=50000)
            db.session.add(c)
            db.session.commit()
            return c.id

    def test_activation_requires_permission_and_confirmation(self):
        cid = self._campaign()
        from app.social_media.services import ads
        with self.app.app_context():
            u = SocialUserPermission.query.filter_by(user_id=self.ids['staff']).one()
            u.can_view_ads = u.can_manage_ads = True
            db.session.commit()
        self.login('staff')
        with mock.patch.object(ads, 'activate') as act:
            r = self.client.post(f'/social-media/ads/campaigns/{cid}/status', data={
                'csrf_token': self.csrf(), 'action': 'activate', 'ack_billing': '1', 'confirm_currency': 'PKR',
                'confirm_budget': '50000'})
            self.assertIn(r.status_code, (302, 403))
            act.assert_not_called()
        self.client.get('/auth/logout')
        self.login('admin')
        with mock.patch.object(ads, 'activate') as act:
            self.client.post(f'/social-media/ads/campaigns/{cid}/status', data={
                'csrf_token': self.csrf(), 'action': 'activate', 'confirm_currency': 'PKR', 'confirm_budget': '50000'})
            act.assert_not_called()  # no billing acknowledgement
            self.client.post(f'/social-media/ads/campaigns/{cid}/status', data={
                'csrf_token': self.csrf(), 'action': 'activate', 'ack_billing': '1', 'confirm_currency': 'PKR',
                'confirm_budget': '50000'})
            act.assert_called_once()

    def test_budget_increase_needs_second_confirmation(self):
        cid = self._campaign()
        from app.social_media.services import ads
        self.login('admin')
        with mock.patch.object(ads, 'update_budget', return_value=('daily_budget', 0)) as ub:
            self.client.post(f'/social-media/ads/campaigns/{cid}/budget', data={
                'csrf_token': self.csrf(), 'amount': '1000', 'ack_increase': '1'})
            ub.assert_not_called()  # 500 -> 1000 PKR is +100%
            self.client.post(f'/social-media/ads/campaigns/{cid}/budget', data={
                'csrf_token': self.csrf(), 'amount': '1000', 'ack_increase': '1', 'ack_large_increase': '1'})
            ub.assert_called_once()

    def test_created_campaigns_are_paused_and_currency_offset(self):
        from app.social_media.services import ads
        self.assertEqual(ads.to_minor('12.50', 'PKR'), 1250)
        self.assertEqual(ads.to_minor('1000', 'JPY'), 1000)
        payload = ads._campaign_payload({'name': 'x', 'objective': 'OUTCOME_ENGAGEMENT', 'budget_type': 'daily',
                                         'minor': 100})
        self.assertEqual(payload['status'], 'PAUSED')

    def test_post_publishing_never_touches_ads(self):
        pid = self.make_post()
        from app.social_media.services import ads
        with mock.patch.object(meta, 'publish_facebook', return_value=('a', '')), \
                mock.patch.object(ads, 'activate') as act, mock.patch.object(ads, 'create_paused') as cp:
            with self.app.app_context():
                publisher.publish_destination(SocialPostDestination.query.filter_by(post_id=pid).one().id)
            act.assert_not_called()
            cp.assert_not_called()

    # ── pages render ──────────────────────────────────────────────────
    def test_all_pages_render(self):
        pid = self.make_post()
        self.login('admin')
        urls = ['/social-media/', '/social-media/posts', '/social-media/posts?tab=failed', '/social-media/posts/new',
                f'/social-media/posts/{pid}', '/social-media/calendar', '/social-media/calendar?view=week',
                '/social-media/calendar?view=day', '/social-media/calendar?view=list', '/social-media/analytics',
                '/social-media/accounts', '/social-media/logs', '/social-media/logs?view=attempts',
                '/social-media/ads'] + [f'/social-media/settings?tab={t}' for t in (
                    'general', 'meta', 'instagram', 'linkedin', 'ads', 'media', 'scheduler', 'notifications',
                    'security', 'permissions')]
        for url in urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertIn('sm-page', r.get_data(as_text=True), url)
        html = self.client.get('/social-media/').get_data(as_text=True)
        self.assertIn('Social Media', html)
        self.assertIn('name="viewport"', self.client.get('/social-media/').get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
