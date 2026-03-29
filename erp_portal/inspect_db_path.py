from app import create_app, db
app = create_app()
with app.app_context():
    print('SQLALCHEMY_DATABASE_URI', app.config['SQLALCHEMY_DATABASE_URI'])
    print('engine:', db.engine.url)
    print('is sqlite', 'sqlite' in str(db.engine.url))
    if 'sqlite' in str(db.engine.url):
        import sqlite3, os
        db_path = db.engine.url.database
        print('db_path', db_path)
        print('exists:', os.path.exists(db_path))
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print('tables:', [r[0] for r in c.fetchall()])
        conn.close()
