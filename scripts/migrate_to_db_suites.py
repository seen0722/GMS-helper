import sys
import os

# Add parent dir to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import models, database
from sqlalchemy.orm import Session

def migrate_suites():
    # Create tables
    models.Base.metadata.create_all(bind=database.engine)
    
    db = database.SessionLocal()
    try:
        suites = [
            {
                "name": "CTS", 
                "display_name": "CTS", 
                "sort_order": 10, 
                "match_rule": "Standard",
                "is_required": 1,
                "description": "Compatibility Test Suite"
            },
            {
                "name": "CTSonGSI", 
                "display_name": "CTS on GSI", 
                "sort_order": 20, 
                "match_rule": "GSI",
                "is_required": 1,
                "description": "CTS running on Generic System Image"
            },
            {
                "name": "VTS", 
                "display_name": "VTS", 
                "sort_order": 30, 
                "match_rule": "Standard",
                "is_required": 1,
                "description": "Vendor Test Suite"
            },
            {
                "name": "GTS", 
                "display_name": "GTS", 
                "sort_order": 40, 
                "match_rule": "Standard",
                "is_required": 1,
                "description": "Google Mobile Services Test Suite"
            },
            {
                "name": "STS", 
                "display_name": "STS", 
                "sort_order": 50, 
                "match_rule": "Standard",
                "is_required": 1,
                "description": "Security Test Suite"
            }
        ]
        
        print("Seeding Test Suite Configuration...")
        for s in suites:
            existing = db.query(models.TestSuiteConfig).filter(models.TestSuiteConfig.name == s["name"]).first()
            if not existing:
                config = models.TestSuiteConfig(**s)
                db.add(config)
                print(f"Added: {s['name']}")
            else:
                print(f"Skipped (exists): {s['name']}")
        
        db.commit()
        print("Migration Completed Successfully.")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_suites()
