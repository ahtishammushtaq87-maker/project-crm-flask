import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "instance", "database.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
<<<<<<< HEAD
    # Enable SQLite foreign key constraints for proper cascade deletes
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'check_same_thread': False
        }
    }
=======
    
    @staticmethod
    def init_app(app):
        uri = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "instance", "database.db")}'
        if uri.startswith('sqlite'):
            app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {
                'connect_args': {'check_same_thread': False}
            })
>>>>>>> 817f50840933f800b784ce4d44645bbd5bb0f00c
