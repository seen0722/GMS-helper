from backend.database.database import SessionLocal
from backend.database import models
from sqlalchemy import desc
from datetime import datetime

def check_counts():
    db = SessionLocal()
    
    # Timestamps from XMLs (milliseconds)
    ts1 = 1754631580579
    ts2 = 1754633920975
    
    # Convert to expected DB format if necessary, or just list all runs to find matches.
    # The models.py says start_time is DateTime.
    # Let's list the recent runs and try to match.
    
    print("--- Searching for Runs ---")
    runs = db.query(models.TestRun).order_by(desc(models.TestRun.id)).limit(10).all()
    
    found_runs = []
    
    for r in runs:
        # Check if this looks like our run
        # Convert DB datetime to timestamp to compare?
        # Or just print details
        
        # Count failures
        fail_count = db.query(models.TestCase).filter(models.TestCase.test_run_id == r.id).count()
        # Count modules
        mod_count = db.query(models.TestRunModule).filter(models.TestRunModule.test_run_id == r.id).count()
        
        print(f"Run ID: {r.id}")
        print(f"  Suite: {r.test_suite_name}")
        print(f"  Start: {r.start_display} (DB Time: {r.start_time})")
        print(f"  Failures (Rows in test_cases): {fail_count}")
        print(f"  Modules (Rows in test_run_modules): {mod_count}")
        print("-" * 20)

if __name__ == "__main__":
    check_counts()
