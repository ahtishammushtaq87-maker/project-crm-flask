"""Tests for Forgot password + Settings > Email (SMTP).

Uses a throw-away SQLite file and a fake SMTP server (nothing is really sent):

    venv\\Scripts\\python.exe -m unittest tests.test_system_mail -v
"""
import os
import re
import shutil
import smtplib
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from config import Config  # noqa: E402

_TMP = tempfile.mkdtemp(prefix='system_mail_test_')


class _TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')
    SERVER_NAME = 'crm.test'


from app import create_app, db  # noqa: E402
from app.models import User  # noqa: E402
from app.system_mail.models import MailSettings, PasswordReset  # noqa: E402


class FakeSMTP:
    """Stands in for smtplib.SMTP / SMTP_SSL and records what was sent."""
    sent = []
    fail_login = False
    fail_send = False

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port

    def ehlo(self):
        pass

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        if FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b'5.7.8 Username and Password not accepted')

    def noop(self):
        pass

    def send_message(self, msg):
        if FakeSMTP.fail_send:
            raise smtplib.SMTPServerDisconnected('gone')
        FakeSMTP.sent.append(msg)

    def quit(self):
        pass


class SystemMailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(_TestConfig)
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
        cls.patchers = [mock.patch('app.system_mail.mailer.smtplib.SMTP', FakeSMTP),
                        mock.patch('app.system_mail.mailer.smtplib.SMTP_SSL', FakeSMTP)]
        for p in cls.patchers:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in cls.patchers:
            p.stop()
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        shutil.rmtree(_TMP, ignore_errors=True)

    def setUp(self):
        FakeSMTP.sent, FakeSMTP.fail_login, FakeSMTP.fail_send = [], False, False
        with self.app.app_context():
            with db.engine.connect() as conn:
                conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
                for (name,) in conn.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                    conn.exec_driver_sql(f'DELETE FROM "{name}"')
                conn.commit()
            self._user('admin', 'admin@example.com', role='admin')
            self._user('ali', 'ali@example.com')
            self._user('noemail', 'not-an-email')
            self._user('sleepy', 'sleepy@example.com', is_active=False)
            db.session.add(MailSettings(is_enabled=True, smtp_host='smtp.example.com', smtp_port=587,
                                        security='starttls', smtp_username='crm@example.com',
                                        smtp_password='secret-pw', from_email='crm@example.com'))
            db.session.commit()
        self.client = self.app.test_client()

    @staticmethod
    def _user(username, email, role='user', is_active=True):
        u = User(username=username, email=email, role=role, is_active=is_active)
        u.set_password('realpass1')
        db.session.add(u)
        return u

    # ── helpers ────────────────────────────────────────────────────────
    def csrf(self, url):
        html = self.client.get(url).get_data(as_text=True)
        return re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html).group(1)

    def forgot(self, username):
        """Click "Forgot password?" on the sign-in page with ``username`` typed."""
        token = self.csrf('/auth/login')
        return self.client.post('/auth/forgot-password', data={'csrf_token': token, 'username': username},
                                follow_redirects=True)

    def login(self, username, password):
        token = self.csrf('/auth/login')
        return self.client.post('/auth/login', data={'csrf_token': token, 'username': username,
                                                     'password': password})

    def temp_password_from_email(self):
        body = FakeSMTP.sent[-1].get_body(preferencelist=('plain',)).get_content()
        return re.search(r'Temporary password:\s+(\S{12})', body).group(1)

    def resets(self):
        with self.app.app_context():
            return PasswordReset.query.count()

    # ── forgot password ────────────────────────────────────────────────
    def test_login_page_has_forgot_link(self):
        html = self.client.get('/auth/login').get_data(as_text=True)
        self.assertIn('/auth/forgot-password', html)
        self.assertIn('Forgot password?', html)

    def test_unknown_user_shows_message(self):
        html = self.forgot('nobody').get_data(as_text=True)
        self.assertIn('No user account was found', html)
        self.assertEqual((len(FakeSMTP.sent), self.resets()), (0, 0))

    def test_user_without_valid_email_shows_message(self):
        html = self.forgot('noemail').get_data(as_text=True)
        self.assertIn('does not have a valid email address', html)
        self.assertEqual(len(FakeSMTP.sent), 0)

    def test_inactive_user_shows_message(self):
        html = self.forgot('sleepy').get_data(as_text=True)
        self.assertIn('This account is inactive', html)
        self.assertEqual(len(FakeSMTP.sent), 0)

    def test_not_configured_shows_message(self):
        with self.app.app_context():
            MailSettings.query.update({'is_enabled': False})
            db.session.commit()
        html = self.forgot('ali').get_data(as_text=True)
        self.assertIn('not set up yet', html)
        self.assertEqual(len(FakeSMTP.sent), 0)

    def test_reset_by_username_and_by_email(self):
        for ident in ('ali', 'ALI@example.com'):
            with self.subTest(ident):
                FakeSMTP.sent = []
                with self.app.app_context():
                    PasswordReset.query.delete()
                    db.session.commit()
                html = self.forgot(ident).get_data(as_text=True)
                self.assertIn('We emailed your username and a temporary password to a***i@e***e.com', html)
                plain = FakeSMTP.sent[0].get_body(preferencelist=('plain',)).get_content()
                self.assertIn('Username:           ali', plain)
                html_mail = FakeSMTP.sent[0].get_body(preferencelist=('html',)).get_content()
                self.assertIn('>Sign in</a>', html_mail)
                self.assertIn('http://crm.test/auth/login', html_mail)
                self.assertEqual(len(FakeSMTP.sent), 1)
                msg = FakeSMTP.sent[0]
                self.assertEqual(msg['To'], 'ali@example.com')
                self.assertIn('temporary password', msg['Subject'])
                self.assertIsNotNone(msg.get_body(preferencelist=('html',)))
                temp = self.temp_password_from_email()
                with self.app.app_context():
                    r = PasswordReset.query.one()
                    self.assertNotIn(temp, r.temp_password_hash)  # stored hashed
                    self.assertTrue(User.query.filter_by(username='ali').one().check_password('realpass1'))

    def test_temp_password_login_forces_change_and_is_single_use(self):
        self.forgot('ali')
        temp = self.temp_password_from_email()
        r = self.login('ali', temp)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/auth/change-password', r.headers['Location'])
        # every other page sends them back to change their password
        r = self.client.get('/sales-target/')
        self.assertIn('/auth/change-password', r.headers['Location'])
        token = self.csrf('/auth/change-password')
        r = self.client.post('/auth/change-password', data={'csrf_token': token, 'new_password': 'brandnew99',
                                                            'confirm_password': 'brandnew99'})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('change-password', r.headers['Location'])
        with self.app.app_context():
            self.assertTrue(User.query.filter_by(username='ali').one().check_password('brandnew99'))
        self.client.get('/auth/logout')
        # the temporary password can't be used again
        r = self.login('ali', temp)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Invalid username or password', r.get_data(as_text=True))

    def test_expired_temp_password_rejected(self):
        self.forgot('ali')
        temp = self.temp_password_from_email()
        with self.app.app_context():
            PasswordReset.query.update({'expires_at': datetime.utcnow() - timedelta(minutes=1)})
            db.session.commit()
        r = self.login('ali', temp)
        self.assertEqual(r.status_code, 200)

    def test_real_password_still_works_and_revokes_temp(self):
        self.forgot('ali')
        temp = self.temp_password_from_email()
        self.assertEqual(self.login('ali', 'realpass1').status_code, 302)
        self.client.get('/auth/logout')
        self.assertEqual(self.login('ali', temp).status_code, 200)  # revoked

    def test_cooldown_between_requests(self):
        self.forgot('ali')
        html = self.forgot('ali').get_data(as_text=True)
        self.assertIn('was just sent', html)
        self.assertEqual(len(FakeSMTP.sent), 1)

    def test_smtp_failure_reports_and_keeps_nothing(self):
        FakeSMTP.fail_send = True
        html = self.forgot('ali').get_data(as_text=True)
        self.assertIn('could not be emailed', html)
        self.assertEqual(self.resets(), 0)

    def test_forgot_requires_csrf(self):
        self.client.post('/auth/forgot-password', data={'username': 'ali'})
        self.assertEqual(len(FakeSMTP.sent), 0)

    def test_no_separate_forgot_page(self):
        r = self.client.get('/auth/forgot-password')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/auth/login', r.headers['Location'])

    def test_empty_username_asks_to_type_it(self):
        html = self.forgot('').get_data(as_text=True)
        self.assertIn('Type your username first', html)
        self.assertEqual(len(FakeSMTP.sent), 0)

    def test_change_password_requires_current_password_normally(self):
        self.login('ali', 'realpass1')
        token = self.csrf('/auth/change-password')
        r = self.client.post('/auth/change-password', data={'csrf_token': token, 'current_password': 'wrong',
                                                            'new_password': 'brandnew99',
                                                            'confirm_password': 'brandnew99'})
        self.assertIn('current password is not correct', r.get_data(as_text=True))
        with self.app.app_context():
            self.assertTrue(User.query.filter_by(username='ali').one().check_password('realpass1'))

    # ── settings page ──────────────────────────────────────────────────
    def settings_form(self, **over):
        token = self.csrf('/settings/email/')
        data = {'csrf_token': token, 'is_enabled': 'y', 'smtp_host': 'smtp.gmail.com', 'smtp_port': '587',
                'security': 'starttls', 'smtp_username': 'me@gmail.com', 'smtp_password': '',
                'from_email': 'me@gmail.com', 'from_name': 'My CRM', 'reply_to': '', 'timeout_seconds': '20',
                'test_to': 'me@gmail.com', 'action': 'save'}
        data.update(over)
        return data

    def test_settings_admin_only(self):
        self.login('ali', 'realpass1')
        r = self.client.get('/settings/email/')
        self.assertEqual(r.status_code, 302)

    def test_non_admin_with_settings_permission_cannot_see_or_change_email_settings(self):
        with self.app.app_context():
            u = User.query.filter_by(username='ali').one()
            u.can_view_settings = u.can_edit_settings = True
            db.session.commit()
        self.login('ali', 'realpass1')
        sidebar = self.client.get('/').get_data(as_text=True)
        self.assertIn('Invoice Settings', sidebar)          # sees the Settings menu...
        self.assertNotIn('Email (SMTP)', sidebar)           # ...but not the email item
        self.assertNotIn('/settings/email', sidebar)
        r = self.client.post('/settings/email/', data={'smtp_host': 'evil.example.com', 'action': 'save'})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            self.assertEqual(MailSettings.query.one().smtp_host, 'smtp.example.com')
        self.client.get('/auth/logout')
        self.login('admin', 'realpass1')
        self.assertIn('Email (SMTP)', self.client.get('/').get_data(as_text=True))

    def test_settings_save_keeps_password_and_never_shows_it(self):
        self.login('admin', 'realpass1')
        html = self.client.get('/settings/email/').get_data(as_text=True)
        self.assertNotIn('secret-pw', html)
        r = self.client.post('/settings/email/', data=self.settings_form())
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            s = MailSettings.query.one()
            self.assertEqual((s.smtp_host, s.smtp_password), ('smtp.gmail.com', 'secret-pw'))
        self.client.post('/settings/email/', data=self.settings_form(smtp_password='new-pw'))
        with self.app.app_context():
            self.assertEqual(MailSettings.query.one().smtp_password, 'new-pw')

    def test_settings_validation(self):
        self.login('admin', 'realpass1')
        r = self.client.post('/settings/email/', data=self.settings_form(smtp_port='99999', from_email='bad'))
        html = r.get_data(as_text=True)
        self.assertIn('Enter a valid port', html)
        self.assertIn('Enter a valid email address', html)
        with self.app.app_context():
            self.assertEqual(MailSettings.query.one().smtp_host, 'smtp.example.com')

    def test_test_connection_and_send_test_email(self):
        self.login('admin', 'realpass1')
        html = self.client.post('/settings/email/', data=self.settings_form(action='test_connection')).get_data(as_text=True)
        self.assertIn('signed in successfully', html)
        FakeSMTP.fail_login = True
        html = self.client.post('/settings/email/', data=self.settings_form(action='test_connection')).get_data(as_text=True)
        self.assertIn('rejected the username or password', html)
        FakeSMTP.fail_login = False
        html = self.client.post('/settings/email/', data=self.settings_form(action='send_test')).get_data(as_text=True)
        self.assertIn('Email sent to me@gmail.com', html)
        self.assertEqual(FakeSMTP.sent[-1]['To'], 'me@gmail.com')
        with self.app.app_context():
            s = MailSettings.query.one()
            self.assertTrue(s.last_test_ok)
            self.assertEqual(s.smtp_host, 'smtp.example.com')  # testing doesn't save


if __name__ == '__main__':
    unittest.main()
