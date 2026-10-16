"""Tests for the admin "Login as user" feature (throw-away SQLite file):

    venv\\Scripts\\python.exe -m unittest tests.test_impersonation -v
"""
import os
import re
import shutil
import tempfile
import unittest

for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from config import Config  # noqa: E402

_TMP = tempfile.mkdtemp(prefix='impersonation_test_')


class _TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')


from app import create_app, db  # noqa: E402
from app.models import ActivityLog, User  # noqa: E402


class ImpersonationTests(unittest.TestCase):
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
            ids = {}
            for name, role, active, extra in (('admin', 'admin', True, {}), ('boss2', 'admin', True, {}),
                                              ('ali', 'user', True, {'can_view_users': False}),
                                              ('sleepy', 'user', False, {})):
                u = User(username=name, email=f'{name}@example.com', role=role, is_active=active, **extra)
                u.set_password('pass1234')
                db.session.add(u)
                db.session.flush()
                ids[name] = u.id
            db.session.commit()
        self.ids = ids
        self.client = self.app.test_client()

    def login(self, username):
        html = self.client.get('/auth/login').get_data(as_text=True)
        token = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html).group(1)
        r = self.client.post('/auth/login', data={'csrf_token': token, 'username': username, 'password': 'pass1234'})
        self.assertEqual(r.status_code, 302)

    def page_token(self, url='/users/list'):
        html = self.client.get(url).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def whoami(self):
        with self.client.session_transaction() as s:
            return s.get('_user_id')

    def test_users_list_shows_login_button_only_where_allowed(self):
        self.login('admin')
        html = self.client.get('/users/list').get_data(as_text=True)
        self.assertIn(f'/users/impersonate/{self.ids["ali"]}/start', html)
        for name in ('admin', 'boss2', 'sleepy'):
            self.assertNotIn(f'/users/impersonate/{self.ids[name]}/start', html)

    def test_login_as_user_and_return(self):
        self.login('admin')
        token = self.page_token()
        r = self.client.post(f'/users/impersonate/{self.ids["ali"]}/start', data={'csrf_token': token})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.whoami(), str(self.ids['ali']))
        page = self.client.get('/').get_data(as_text=True)
        self.assertIn('You are signed in as ali', page)
        self.assertIn('Return to admin', page)
        # ali's own permissions apply: no User Management
        self.assertEqual(self.client.get('/users/list').status_code, 302)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        r = self.client.post('/users/impersonate/stop', data={'csrf_token': token})
        self.assertEqual(r.status_code, 302)
        self.assertIn('/users/list', r.headers['Location'])
        self.assertEqual(self.whoami(), str(self.ids['admin']))
        self.assertNotIn('You are signed in as', self.client.get('/users/list').get_data(as_text=True))
        with self.app.app_context():
            actions = [a.action for a in ActivityLog.query.order_by(ActivityLog.id).all()]
        self.assertIn('Signed in as user ali', actions)
        self.assertIn('Returned from user ali', actions)

    def test_rules(self):
        self.login('admin')
        token = self.page_token()
        for name in ('admin', 'boss2', 'sleepy'):
            with self.subTest(name):
                self.client.post(f'/users/impersonate/{self.ids[name]}/start', data={'csrf_token': token})
                self.assertEqual(self.whoami(), str(self.ids['admin']))
        self.client.post('/users/impersonate/99999/start', data={'csrf_token': token})
        self.assertEqual(self.whoami(), str(self.ids['admin']))

    def test_requires_csrf_and_admin(self):
        self.login('admin')
        self.client.post(f'/users/impersonate/{self.ids["ali"]}/start', data={})
        self.assertEqual(self.whoami(), str(self.ids['admin']))
        self.client.get('/auth/logout')
        self.login('ali')
        html = self.client.get('/auth/change-password').get_data(as_text=True)   # has a valid form token
        token = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html).group(1)
        self.client.post(f'/users/impersonate/{self.ids["sleepy"]}/start', data={'csrf_token': token})
        self.assertEqual(self.whoami(), str(self.ids['ali']))

    def test_cannot_chain_impersonation(self):
        self.login('admin')
        token = self.page_token()
        self.client.post(f'/users/impersonate/{self.ids["ali"]}/start', data={'csrf_token': token})
        with self.app.app_context():
            u = db.session.get(User, self.ids['sleepy'])
            u.is_active = True
            db.session.commit()
        self.client.post(f'/users/impersonate/{self.ids["sleepy"]}/start', data={'csrf_token': token})
        self.assertEqual(self.whoami(), str(self.ids['ali']))

    def test_logout_clears_and_stale_return_cannot_reach_admin(self):
        self.login('admin')
        token = self.page_token()
        self.client.post(f'/users/impersonate/{self.ids["ali"]}/start', data={'csrf_token': token})
        self.client.get('/auth/logout')
        with self.client.session_transaction() as s:
            self.assertNotIn('impersonation', s)
        # someone else signs in on the same browser: no way back to admin
        self.login('ali')
        with self.client.session_transaction() as s:
            s['impersonation'] = {'admin_id': self.ids['admin'], 'user_id': 12345}  # forged / stale
        page = self.client.get('/').get_data(as_text=True)
        self.assertNotIn('Return to admin', page)
        token = re.search(r'name="csrf_token" (?:type="hidden" )?value="([^"]+)"', page)
        self.client.post('/users/impersonate/stop', data={'csrf_token': token.group(1) if token else ''})
        self.assertEqual(self.whoami(), str(self.ids['ali']))

    def test_return_refused_if_admin_was_demoted(self):
        self.login('admin')
        token = self.page_token()
        self.client.post(f'/users/impersonate/{self.ids["ali"]}/start', data={'csrf_token': token})
        with self.app.app_context():
            db.session.get(User, self.ids['admin']).role = 'user'
            db.session.commit()
        page = self.client.get('/').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        r = self.client.post('/users/impersonate/stop', data={'csrf_token': token})
        self.assertIn('/auth/login', r.headers['Location'])
        self.assertIsNone(self.whoami())


if __name__ == '__main__':
    unittest.main()
