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
            submission = SubmissionService.get_or_create_submission(
                db=db,
                fingerprint=fingerprint,
                suite_name=run.test_suite_name,
                suite_plan=run.suite_plan,
                android_version=run.android_version,
                build_product=run.build_product,
                build_brand=run.build_brand,
                build_model=run.build_model,
                security_patch=run.security_patch
            )

            if run.submission_id != submission.id:
                print(f"Updating Run {run.id}: Submission {run.submission_id} -> {submission.id}")
                run.submission_id = submission.id
            
            # Migration: Update existing submission names to new format if still in default format
            if submission.name.startswith("Submission "):
                brand = run.build_brand or "Unknown"
                model = run.build_model or run.build_product or "Device"
                patch = run.security_patch or "NoPatch"
                
                suffix_label = "Unknown"
                fp_pattern = re.compile(r"^([^:]+):([^/]+)/([^/]+)(/.+)$")
                m = fp_pattern.match(run.device_fingerprint)
                if m:
                    raw_suffix = m.group(4).lstrip('/')
                    suffix_label = raw_suffix.split('_')[0].split(':')[0]
                
                new_name = f"{brand} {model} - {patch} (Build: {suffix_label})"
                if submission.name != new_name:
                    print(f"Renaming Submission {submission.id}: {submission.name} -> {new_name}")
                    submission.name = new_name
                    db.flush()
        
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
