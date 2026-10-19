"""Every action in the Media module is recorded in the Activity Log.

Throw-away SQLite DB and a throw-away static folder (no files land in the
real app/static):

    venv\\Scripts\\python.exe -m unittest tests.test_media_activity -v
"""
import io
import os
import shutil
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix='media_activity_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')
for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from app import create_app, db  # noqa: E402
from app.models import User, Media, MediaFolder, ActivityLog  # noqa: E402


class MediaActivityTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.static_folder = os.path.join(_TMP, 'static')
        os.makedirs(cls.app.static_folder, exist_ok=True)
        with cls.app.app_context():
            db.create_all()
            admin = User(username='admin', email='admin@example.com', role='admin')
            admin.set_password('pw')
            db.session.add(admin)
            db.session.commit()
            cls.admin_id = admin.id

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
        for model in (ActivityLog, Media, MediaFolder):
            model.query.delete()
        db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.admin_id)
            sess['_fresh'] = True

    def _cleanup(self):
        db.session.rollback()
        db.session.remove()
        self.ctx.pop()

    def logs(self):
        db.session.expire_all()
        return [(l.module, l.action, l.details or '', l.user_id)
                for l in ActivityLog.query.filter_by(module='Media').order_by(ActivityLog.id).all()]

    def upload(self, name='report.pdf', folder_id=''):
        r = self.client.post('/media/upload', data={'file': (io.BytesIO(b'%PDF-1.4 test'), name, 'application/pdf'),
                                                    'folder_id': str(folder_id)},
                             content_type='multipart/form-data')
        self.assertEqual(r.status_code, 200)
        return r.get_json()['id']

    def test_every_action_is_logged(self):
        self.client.post('/media/folder/create', data={'name': 'Invoices', 'parent_id': ''})
        folder = MediaFolder.query.one()
        self.client.post(f'/media/folder/{folder.id}/rename', data={'name': 'Bills'})
        file_id = self.upload('report.pdf')
        self.client.get(f'/media/preview/{file_id}')
        self.client.get(f'/media/view/{file_id}')          # the preview's own fetch: not logged again
        self.client.get(f'/media/download/{file_id}')
        self.client.post('/media/move', json={'items': [{'type': 'file', 'id': file_id}],
                                               'target_folder_id': folder.id})
        self.client.post(f'/media/delete/{file_id}')
        self.client.post(f'/media/folder/{folder.id}/delete')

        actions = [a for _, a, _, _ in self.logs()]
        self.assertEqual(actions, [
            'Created folder: Invoices',
            'Renamed folder: Invoices → Bills',
            'Uploaded file: report.pdf',
            'Viewed file: report.pdf',
            'Downloaded file: report.pdf',
            'Moved 1 item(s) to Media Library / Bills',
            'Deleted file: report.pdf',
            'Deleted folder: Bills',
        ])
        self.assertTrue(all(uid == self.admin_id for _, _, _, uid in self.logs()))
        details = {a: d for _, a, d, _ in self.logs()}
        self.assertIn('Folder: Media Library', details['Uploaded file: report.pdf'])
        self.assertIn('"report.pdf"', details['Moved 1 item(s) to Media Library / Bills'])
        self.assertIn('Folder: Media Library / Bills', details['Deleted file: report.pdf'])

    def test_upload_into_folder_records_its_path(self):
        self.client.post('/media/folder/create', data={'name': 'HR', 'parent_id': ''})
        hr = MediaFolder.query.one()
        self.client.post('/media/folder/create', data={'name': 'CVs', 'parent_id': str(hr.id)})
        cvs = MediaFolder.query.filter_by(name='CVs').one()
        self.upload('cv.pdf', folder_id=cvs.id)
        self.assertIn('Folder: Media Library / HR / CVs', self.logs()[-1][2])

    def test_refused_actions_are_not_logged(self):
        self.client.post('/media/folder/create', data={'name': '', 'parent_id': ''})   # invalid name
        self.client.post('/media/move', json={'items': [], 'target_folder_id': None})  # nothing moved
        self.assertEqual(self.logs(), [])

    def test_missing_file_is_explained_not_downloaded(self):
        # A record whose file isn't on this server (e.g. after restoring a
        # database from another machine without its uploads folder).
        db.session.add(Media(filename='IMG-1.jpg', filepath='uploads/media/20260620_IMG-1.jpg',
                             file_type='image/jpeg', file_size=10, uploaded_by_id=self.admin_id))
        db.session.commit()
        doc = Media.query.filter_by(filename='IMG-1.jpg').one()
        present = self.upload('ok.pdf')

        page = self.client.get('/media/').get_data(as_text=True)
        self.assertEqual(page.count('File missing</span>'), 1)          # only the missing one
        self.assertIn(f'data-id="{doc.id}"', page)

        preview = self.client.get(f'/media/preview/{doc.id}').get_data(as_text=True)
        self.assertIn('The file is missing on this server', preview)
        self.assertIn('app/static/uploads/media/20260620_IMG-1.jpg', preview)
        self.assertNotIn('Download IMG-1.jpg', preview)

        r = self.client.get(f'/media/download/{doc.id}')
        self.assertEqual(r.status_code, 302)                           # message, not an error page
        self.assertNotIn('Downloaded file: IMG-1.jpg', [a for _, a, _, _ in self.logs()])
        self.assertEqual(self.client.get(f'/media/download/{present}').status_code, 200)

    def test_activity_page_lists_media(self):
        self.upload()
        html = self.client.get('/activity-log/?module=Media').get_data(as_text=True)
        self.assertIn('Uploaded file: report.pdf', html)
        self.assertIn('>Media<', html)                     # in the module filter


if __name__ == '__main__':
    unittest.main()
