import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.database import models
from backend.database.database import SQLALCHEMY_DATABASE_URL

# Setup DB connection
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def migrate_products():
    print("Starting Product Column Migration...")
    
    # Refresh metadata/mapping if needed, but since we are running fresh script it should be fine.
    
    submissions = db.query(models.Submission).all()
    count = 0
    
    for sub in submissions:
        # Infer product from the first test run associated with this submission
        # or from target_fingerprint if runs are missing (less reliable)
        
        product_name = "Unknown"
        
        if sub.test_runs:
            # Pick the first run (or any run, assuming a submission is for one product)
            first_run = sub.test_runs[0]
            if first_run.build_product and first_run.build_product != "Unknown":
                product_name = first_run.build_product
                
        # Update
        sub.product = product_name
        print(f"Submission {sub.id}: {sub.name} -> Product: {product_name}")
        count += 1
        
    db.commit()
    print(f"Migration Complete. Updated {count} submissions.")

if __name__ == "__main__":
    # Ensure column exists
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN product VARCHAR"))
            conn.commit()
            print("Added 'product' column to submissions table.")
    except Exception as e:
        print(f"Column add skipped (likely exists or error): {e}")

    migrate_products()
