from app import create_app, db
from sqlalchemy import text

app = create_app()

def add_returns_column():
    with app.app_context():
        with db.engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN can_view_returns BOOLEAN DEFAULT 1"))
                conn.commit()
                print("Successfully added can_view_returns column!")
            except Exception as e:
                print(f"Column may already exist or error: {e}")

if __name__ == "__main__":
    add_returns_column()
