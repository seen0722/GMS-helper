
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.database import models, database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def reset_analysis(run_id):
    db = next(database.get_db())
    try:
        print(f"Resetting analysis for Run #{run_id}...")
        
        # 1. Find all FailureAnalysis records linked to this run
        analyses = db.query(models.FailureAnalysis).join(models.TestCase).filter(
            models.TestCase.test_run_id == run_id
        ).all()
        
        print(f"Found {len(analyses)} analysis records to delete.")
        
        # 2. Delete them
        for analysis in analyses:
            db.delete(analysis)
            
        # 3. Reset Run Status
        run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
        if run:
            run.analysis_status = "pending"
            print(f"Run status reset to 'pending'.")
            
        db.commit()
        print("Reset complete.")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/reset_analysis.py <run_id>")
        sys.exit(1)
    
    reset_analysis(int(sys.argv[1]))
