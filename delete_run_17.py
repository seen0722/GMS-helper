#!/usr/bin/env python3
"""Delete run #17 from the database."""

from backend.database.database import SessionLocal
from backend.database import models

def delete_run(run_id: int):
    db = SessionLocal()
    try:
        run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
        if not run:
            print(f"Run #{run_id} not found")
            return
        
        print(f"Deleting run #{run_id}: {run.test_suite_name}")
        print(f"  - Total tests: {run.total_tests}")
        print(f"  - Device: {run.device_fingerprint}")
        
        db.delete(run)
        db.commit()
        print(f"✓ Run #{run_id} deleted successfully!")
        
    except Exception as e:
        print(f"Error deleting run: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    delete_run(17)
