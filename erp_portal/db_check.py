import os, sqlite3
from app import create_app, db

app = create_app()
with app.app_context():
    uri = app.config['SQLALCHEMY_DATABASE_URI']
    db_path = uri.replace('sqlite:///', '')
    print('db_path from URI:', db_path, 'exists', os.path.exists(db_path))

    # Check instance folder
    instance_db = os.path.join(app.instance_path, 'database.db')
    print('instance db:', instance_db, 'exists', os.path.exists(instance_db))

    actual_db = instance_db if os.path.exists(instance_db) else db_path
    print('using db:', actual_db)

    conn = sqlite3.connect(actual_db)
    c = conn.cursor()
    c.execute('SELECT name FROM sqlite_master WHERE type="table" ORDER BY name')
    tables = c.fetchall()
    print('tables:', tables)
    if tables:
        for table in tables:
            c.execute(f'PRAGMA table_info({table[0]})')
            print(f'Columns in {table[0]}:', c.fetchall())
    conn.close()
