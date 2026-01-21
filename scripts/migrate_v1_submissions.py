import sys
import os
# Add parent dir to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.database import engine, Base
from backend.database import models
from sqlalchemy import text, inspect

def run_migration():
    print("Running Phase 1 Migration: Submissions...")
    
    # 1. Create new tables (submissions)
    print("Creating new tables from models...")
    Base.metadata.create_all(bind=engine)
    
    # 2. Check and Alter existing tables
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('test_runs')]
    
    if 'submission_id' not in columns:
        print("Adding submission_id to test_runs table...")
        with engine.connect() as conn:
            # SQLite supports adding column, but adding FK constraint via ALTER is limited.
            # We add the column first. FK enforcement depends on SQLite pragma.
            conn.execute(text("ALTER TABLE test_runs ADD COLUMN submission_id INTEGER"))
            print("Column submission_id added.")
            conn.commit()
    else:
        print("Column submission_id already exists.")

    print("Migration complete.")

if __name__ == "__main__":
    run_migration()
