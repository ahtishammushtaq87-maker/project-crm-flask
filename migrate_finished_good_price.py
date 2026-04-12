"""
Migration script to add finished_good_price column to products table
"""
from app import create_app, db
from sqlalchemy import text
import os

def migrate():
    app = create_app()
    with app.app_context():
        engine = db.engine
        
        # Check if column already exists
        with engine.connect() as conn:
            # For SQLite
            if 'sqlite' in str(engine.url):
                result = conn.execute(text("PRAGMA table_info(products)"))
                columns = [row[1] for row in result]
                
                if 'finished_good_price' not in columns:
                    print("Adding finished_good_price column to products table...")
                    conn.execute(text("ALTER TABLE products ADD COLUMN finished_good_price FLOAT"))
                    conn.commit()
                    print("Column added successfully!")
                else:
                    print("Column finished_good_price already exists.")
            
            # For PostgreSQL
            elif 'postgresql' in str(engine.url):
                result = conn.execute(text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'products' AND column_name = 'finished_good_price'
                """))
                
                if result.fetchone() is None:
                    print("Adding finished_good_price column to products table...")
                    conn.execute(text("ALTER TABLE products ADD COLUMN finished_good_price FLOAT"))
                    conn.commit()
                    print("Column added successfully!")
                else:
                    print("Column finished_good_price already exists.")

if __name__ == '__main__':
    migrate()