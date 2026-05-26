from app import create_app, db
from sqlalchemy import text

app = create_app()

def migrate():
    with app.app_context():
        # Check and add warehouse_id to tool_receiving_items
        try:
            db.session.execute(text("ALTER TABLE tool_receiving_items ADD COLUMN warehouse_id INTEGER REFERENCES warehouses(id)"))
            print("Added warehouse_id to tool_receiving_items")
        except Exception as e:
            print(f"Error for tool_receiving_items (might already exist): {e}")

        # Check and add warehouse_id to tool_delivering_items
        try:
            db.session.execute(text("ALTER TABLE tool_delivering_items ADD COLUMN warehouse_id INTEGER REFERENCES warehouses(id)"))
            print("Added warehouse_id to tool_delivering_items")
        except Exception as e:
            print(f"Error for tool_delivering_items (might already exist): {e}")

        # Create indexes
        try:
            db.session.execute(text("CREATE INDEX ix_tool_receiving_items_warehouse_id ON tool_receiving_items (warehouse_id)"))
            print("Created index for tool_receiving_items")
        except Exception as e:
            pass

        try:
            db.session.execute(text("CREATE INDEX ix_tool_delivering_items_warehouse_id ON tool_delivering_items (warehouse_id)"))
            print("Created index for tool_delivering_items")
        except Exception as e:
            pass

        db.session.commit()
        print("Migration complete!")

if __name__ == '__main__':
    migrate()
