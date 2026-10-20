"""Sales Recovery: Mute All / Unmute All buttons on the dashboard.

Runs against a throw-away SQLite file, never the real instance/database.db:

    venv\\Scripts\\python.exe -m unittest tests.test_recovery_mute_all -v
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime

_TMP = tempfile.mkdtemp(prefix='recovery_mute_all_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')
for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from app import create_app, db  # noqa: E402
from app.models import (User, Customer, Sale, Salesman, RecoveryTask, RecoveryLog, Task,  # noqa: E402
                        ActivityLog)


class RecoveryMuteAllTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
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
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self._cleanup)
        self._wipe()
        self._seed()
        self.client = self.app.test_client()
        self.login(self.admin)

    def _cleanup(self):
        db.session.rollback()
        db.session.remove()
        self.ctx.pop()

    @staticmethod
    def _wipe():
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
            for (name,) in conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")):
                conn.exec_driver_sql(f'DELETE FROM "{name}"')
            conn.commit()
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')

    def _user(self, name, **kw):
        u = User(username=name, email=f'{name}@example.com', **kw)
        u.set_password('pw')
        db.session.add(u)
        db.session.flush()
        return u

    def _seed(self):
        self.admin = self._user('admin', role='admin')
        self.viewer = self._user('viewer', can_view_recovery=True)
        self.rep = self._user('rep', is_active=True)
        self.salesman = Salesman(name='Ali', is_active=True, user_id=self.rep.id)
        db.session.add(self.salesman)
        self.c1, self.c2 = Customer(name='Acme'), Customer(name='Beta')
        db.session.add_all([self.c1, self.c2])
        db.session.flush()
        self.tasks = []
        for i, (cust, status) in enumerate([(self.c1, 'OVERDUE'), (self.c1, 'OVERDUE'),
                                            (self.c2, 'FOLLOW_UP_REQUIRED'), (self.c2, 'CLOSED_PAID')]):
            sale = Sale(invoice_number=f'INV-{i}', customer_id=cust.id, date=datetime(2026, 9, 1),
                        subtotal=100, total=100, paid_amount=0, is_approved=True, status='unpaid',
                        salesman_id=self.salesman.id)
            db.session.add(sale)
            db.session.flush()
            t = RecoveryTask(invoice_id=sale.id, salesman_id=self.salesman.id, recovery_status=status)
            db.session.add(t)
            db.session.flush()
            self.tasks.append(t)
        self.open_tasks = self.tasks[:3]
        # An open popup reminder for each customer group
        for t in (self.tasks[0], self.tasks[2]):
            db.session.add(Task(title='Recovery reminder', assigned_to_id=self.rep.id, created_by_id=self.rep.id,
                                recovery_task_id=t.id, linked_invoice_id=t.invoice_id, status='Pending',
                                reminder_at=datetime(2026, 9, 2)))
        db.session.commit()

    def login(self, user):
        from flask import g
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
        g.pop('_login_user', None)

    def post(self, action):
        return self.client.post('/recovery/mute-all', data={'action': action})

    def state(self):
        db.session.expire_all()
        return [bool(db.session.get(RecoveryTask, t.id).is_muted) for t in self.tasks]

    def open_reminders(self):
        return Task.query.filter(Task.recovery_task_id.isnot(None),
                                 Task.status.in_(['Pending', 'In Progress'])).count()

    def test_mute_all_mutes_every_open_invoice_and_stops_reminders(self):
        r = self.post('mute')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.state(), [True, True, True, False])   # the closed one is left alone
        self.assertEqual(self.open_reminders(), 0)                   # popups + timers stopped
        self.assertEqual(RecoveryLog.query.filter(RecoveryLog.note.like('%(Mute All)%')).count(), 3)
        self.assertEqual(ActivityLog.query.filter_by(module='Recovery').one().action,
                         'Muted all recovery notifications')

    def test_unmute_all_restarts_reminders_but_not_for_on_hold(self):
        self.post('mute')
        held = db.session.get(RecoveryTask, self.tasks[2].id)
        held.is_on_hold = True
        db.session.commit()
        self.post('unmute')
        self.assertEqual(self.state(), [False, False, False, False])
        reminders = Task.query.filter(Task.status == 'Pending').all()
        self.assertEqual(len(reminders), 1)                          # one popup for Acme's group
        self.assertIn(reminders[0].recovery_task_id, {self.tasks[0].id, self.tasks[1].id})

    def test_mute_all_only_changes_the_unmuted_ones(self):
        already = db.session.get(RecoveryTask, self.tasks[1].id)
        already.is_muted = True
        db.session.commit()
        self.post('mute')
        self.assertEqual(RecoveryLog.query.filter(RecoveryLog.note.like('%(Mute All)%')).count(), 2)

    def test_viewer_cannot_mute_all(self):
        self.login(self.viewer)
        self.post('mute')
        self.assertEqual(self.state(), [False, False, False, False])

    def test_dashboard_shows_the_buttons(self):
        html = self.client.get('/recovery/').get_data(as_text=True)
        self.assertIn('Mute All', html)
        self.assertNotIn('Unmute All', html)                         # nothing muted yet
        self.post('mute')
        html = self.client.get('/recovery/').get_data(as_text=True)
        self.assertIn('Unmute All', html)
        self.assertNotIn('> Mute All', html)                         # everything is muted
        self.login(self.viewer)
        self.assertNotIn('/recovery/mute-all', self.client.get('/recovery/').get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
