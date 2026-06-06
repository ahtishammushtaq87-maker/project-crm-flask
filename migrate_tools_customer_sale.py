import os
import sys

# Add the project root to the python path
sys.path.append(os.getcwd())

from app import create_app, db
from sqlalchemy import text

app = create_app()

def migrate():
    with app.app_context():
        try:
            # Check for customer_id and sale_id in tool_receiving
            with db.engine.connect() as conn:
                # Flask-SQLAlchemy with SQLite or MySQL
                # we'll use a safer approach - try to add columns and catch error if they exist
                
                print("Checking tool_receiving table...")
                try:
                    conn.execute(text("ALTER TABLE tool_receiving ADD COLUMN customer_id INTEGER"))
                    print("Added customer_id to tool_receiving")
                except Exception as e:
                    print(f"Note: customer_id in tool_receiving might already exist: {e}")

                try:
                    conn.execute(text("ALTER TABLE tool_receiving ADD COLUMN sale_id INTEGER"))
                    print("Added sale_id to tool_receiving")
                except Exception as e:
                    print(f"Note: sale_id in tool_receiving might already exist: {e}")

                print("Checking tool_delivering table...")
                try:
                    conn.execute(text("ALTER TABLE tool_delivering ADD COLUMN customer_id INTEGER"))
                    print("Added customer_id to tool_delivering")
                except Exception as e:
                    print(f"Note: customer_id in tool_delivering might already exist: {e}")

                try:
                    conn.execute(text("ALTER TABLE tool_delivering ADD COLUMN sale_id INTEGER"))
                    print("Added sale_id to tool_delivering")
                except Exception as e:
                    print(f"Note: sale_id in tool_delivering might already exist: {e}")

                conn.commit()
                print("Migration successful!")
        except Exception as e:
            print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
