import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.database.database import SQLALCHEMY_DATABASE_URL

# Setup DB connection
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def add_lock_column():
    print("Migrating 'is_locked' column...")
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN is_locked BOOLEAN DEFAULT 0"))
            conn.commit()
            print("Added 'is_locked' column to submissions table.")
    except Exception as e:
        print(f"Column add skipped (likely exists): {e}")

if __name__ == "__main__":
    add_lock_column()
