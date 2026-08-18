import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "instance", "database.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    @staticmethod
    def init_app(app):
        uri = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "instance", "database.db")}'
        if uri.startswith('sqlite'):
            # check_same_thread=False only disables SQLite's own guard against
            # cross-thread use of one connection — it does NOT make that safe
            # on its own. Without pinning the pool to NullPool, concurrent
            # requests (multiple gunicorn threads, or an async worker class)
            # can end up sharing/reusing the same underlying connection mid-
            # transaction, corrupting each other's view of just-committed rows
            # (surfaces as spurious ObjectDeletedError on rows that were only
            # just written). NullPool hands out a brand-new, dedicated SQLite
            # connection per checkout and closes it on return, so no two
            # concurrent requests ever touch the same connection object.
            from sqlalchemy.pool import NullPool
            app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {
                'connect_args': {'check_same_thread': False},
                'poolclass': NullPool,
            })