import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.database import SessionLocal
from backend.database import models
from backend.services.submission_service import SubmissionService

def regroup():
    db = SessionLocal()
    try:
        # Fetch all runs ordered by ID (chronological)
        runs = db.query(models.TestRun).order_by(models.TestRun.id).all()
        
        print(f"Repairing {len(runs)} runs using centralized SubmissionService...")

        for run in runs:
            fingerprint = run.device_fingerprint
            if not fingerprint or fingerprint == "Pending..." or fingerprint == "Unknown":
                continue

            # Identify target submission using centralized logic
            # Note: We reuse existing submissions because the service checks for matches
            # The service returns existing if match found, or creates new if not.
            submission = SubmissionService.get_or_create_submission(
                db=db,
                fingerprint=fingerprint,
                suite_name=run.test_suite_name,
                suite_plan=run.suite_plan,
                android_version=run.android_version,
                build_product=run.build_product
            )

            if run.submission_id != submission.id:
                print(f"Updating Run {run.id}: Submission {run.submission_id} -> {submission.id}")
                run.submission_id = submission.id
        
        db.commit()
        print("Success: Database repair completed.")
        
        # Cleanup: Remove submissions with no runs
        unused = db.query(models.Submission).filter(~models.Submission.test_runs.any()).all()
        if unused:
            print(f"Cleaning up {len(unused)} empty submissions...")
            for u in unused:
                db.delete(u)
            db.commit()

    except Exception as e:
        print(f"Error during repair: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    regroup()
