"""Tests for the Backup module's "Keep" checkbox (protect a backup from the
10-backup retention).

Runs against a throw-away SQLite file, never the real instance/database.db:

    venv\\Scripts\\python.exe -m unittest tests.test_backup_keep -v
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

_TMP = tempfile.mkdtemp(prefix='backup_keep_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')
for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from app import create_app, db  # noqa: E402
from app.models import User, DatabaseBackup  # noqa: E402
from app.routes import backup as bk  # noqa: E402

BACKUP_DIR = os.path.join(_TMP, 'backups')


class BackupKeepTestCase(unittest.TestCase):
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
        self.ctx = self.app.test_request_context()
        self.ctx.push()
        self.addCleanup(self._cleanup)
        self._wipe()
        shutil.rmtree(BACKUP_DIR, ignore_errors=True)
        self.admin = User(username='admin', email='admin@example.com', role='admin')
        self.admin.set_password('pw')
        db.session.add(self.admin)
        db.session.commit()
        self.client = self.app.test_client()
        from flask import g
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.admin.id)
            sess['_fresh'] = True
        g.pop('_login_user', None)
        self._n = 0

    def _cleanup(self):
        db.session.rollback()
        db.session.remove()
        self.ctx.pop()

    @staticmethod
    def _wipe():
        """Empty every table (activity log rows reference users, so FKs are off
        while wiping; the PRAGMA must run before the transaction starts)."""
        from sqlalchemy import text
        db.session.remove()
        with db.engine.connect() as conn:
            conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
            tables = [r[0] for r in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))]
            for name in tables:
                conn.exec_driver_sql(f'DELETE FROM "{name}"')
            conn.commit()
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')

    def make(self):
        """Create a real backup; give it a distinct, increasing created_at so
        'newest' is unambiguous even when created in the same second."""
        b = bk.create_backup(backup_type='manual')
        self._n += 1
        b.created_at = datetime(2026, 1, 1) + timedelta(minutes=self._n)
        db.session.commit()
        return b

    def ids(self):
        db.session.expire_all()
        return {b.id for b in DatabaseBackup.query.all()}

    def keep(self, backup, on=True):
        return self.client.post(f'/backup/{backup.id}/protect', data={'keep': '1' if on else '0'})

    def test_kept_backup_survives_the_limit(self):
        first = self.make()
        self.keep(first)
        made = [self.make() for _ in range(12)]
        ids = self.ids()
        self.assertIn(first.id, ids)                                 # kept, though the oldest
        self.assertEqual(len(ids), bk.MAX_BACKUPS + 1)               # newest 10 + the kept one
        self.assertEqual(ids - {first.id}, {b.id for b in made[-bk.MAX_BACKUPS:]})
        self.assertTrue(os.path.exists(os.path.join(BACKUP_DIR, first.filename)))
        self.assertTrue(os.path.exists(os.path.join(BACKUP_DIR, first.filename + '.keep')))

    def test_kept_backups_do_not_make_new_ones_delete_themselves(self):
        kept = [self.make() for _ in range(bk.MAX_BACKUPS)]
        for b in kept:
            self.keep(b)
        newest = self.make()
        self.assertIn(newest.id, self.ids())
        self.assertEqual(len(self.ids()), bk.MAX_BACKUPS + 1)

    def test_untick_deletes_only_when_next_backup_is_created(self):
        first = self.make()
        self.keep(first)
        for _ in range(bk.MAX_BACKUPS):
            self.make()
        self.keep(first, on=False)
        page = self.client.get('/backup/').get_data(as_text=True)    # viewing never deletes
        self.assertIn(first.id, self.ids())
        self.assertIn('Removed at next backup', page)
        self.make()                                                  # ...the next backup does
        self.assertNotIn(first.id, self.ids())
        self.assertFalse(os.path.exists(os.path.join(BACKUP_DIR, first.filename)))
        self.assertFalse(os.path.exists(os.path.join(BACKUP_DIR, first.filename + '.keep')))

    def test_manual_delete_removes_a_kept_backup(self):
        b = self.make()
        self.keep(b)
        self.client.post(f'/backup/{b.id}/delete')
        self.assertNotIn(b.id, self.ids())
        self.assertFalse(os.path.exists(os.path.join(BACKUP_DIR, b.filename + '.keep')))

    def test_protection_survives_a_restore(self):
        # A restore swaps in an older database_backups table: the flag is
        # lost there, but the marker file on disk brings it back.
        b = self.make()
        self.keep(b)
        DatabaseBackup.query.filter_by(id=b.id).update({'is_protected': False})
        db.session.commit()
        bk._reconcile_backup_index()
        db.session.expire_all()
        self.assertTrue(db.session.get(DatabaseBackup, b.id).is_protected)
        # ...and a row recreated from disk after a restore is kept too.
        DatabaseBackup.query.filter_by(id=b.id).delete()
        db.session.commit()
        bk._reconcile_backup_index()
        self.assertTrue(DatabaseBackup.query.filter_by(filename=b.filename).one().is_protected)

    def test_page_shows_the_checkbox(self):
        b = self.make()
        html = self.client.get('/backup/').get_data(as_text=True)
        self.assertIn(f'/backup/{b.id}/protect', html)
        self.assertIn('name="keep" value="1"', html)
        self.keep(b)
        html = self.client.get('/backup/').get_data(as_text=True)
        self.assertIn('name="keep" value="0"', html)
        self.assertIn('Kept</span>', html)


if __name__ == '__main__':
    unittest.main()
