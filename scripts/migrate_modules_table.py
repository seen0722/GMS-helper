
from sqlalchemy import create_engine
from backend.database.models import TestRunModule, Base
from backend.database.database import SQLALCHEMY_DATABASE_URL

def migrate():
    print("Migrating test_run_modules table...")
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    # Create the table if it doesn't exist
    # Using SQLAlchemy's create_all which checks for existence
    try:
        TestRunModule.__table__.create(engine)
        print("Table 'test_run_modules' created successfully.")
    except Exception as e:
        print(f"Table might already exist or error: {e}")

if __name__ == "__main__":
    migrate()
