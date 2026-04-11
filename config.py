import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    @staticmethod
    def get_engine_options():
        uri = os.environ.get('DATABASE_URL') or 'sqlite:///database.db'
        if uri.startswith('sqlite'):
            return {'connect_args': {'check_same_thread': False}}
        return {}