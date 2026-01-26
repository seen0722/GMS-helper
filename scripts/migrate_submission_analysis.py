import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import create_engine, text
from backend.database.database import SQLALCHEMY_DATABASE_URL

# Setup DB connection
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def add_analysis_column():
    print("Migrating 'analysis_result' column...")
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN analysis_result TEXT"))
            conn.commit()
            print("Added 'analysis_result' column to submissions table.")
    except Exception as e:
        print(f"Column add skipped (likely exists): {e}")

if __name__ == "__main__":
    add_analysis_column()
