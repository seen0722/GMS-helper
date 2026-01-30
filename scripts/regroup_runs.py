import sys
import os
import re
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

            # Extract metadata if missing (for legacy runs)
            brand = run.build_brand
            model = run.build_model or run.build_product
            device = run.build_device
            patch = run.security_patch
            
            fp_pattern = re.compile(r"^([^:]+):([^/]+)/([^/]+)(/.+)$")
            m = fp_pattern.match(fingerprint)
            
            if m:
                # Fingerprint: Brand/Product/Device:...
                parts = m.group(1).split('/')
                if not brand: brand = parts[0]
                if not model: model = parts[1] if len(parts) > 1 else parts[0]
                if not device: device = parts[2] if len(parts) > 2 else parts[0]
            
            if not patch:
                patch = "NoPatch"

            # Identify target submission using centralized logic
            submission = SubmissionService.get_or_create_submission(
                db=db,
                fingerprint=fingerprint,
                suite_name=run.test_suite_name,
                suite_plan=run.suite_plan,
                android_version=run.android_version,
                build_product=run.build_product,
                build_brand=brand,
                build_model=model,
                build_device=device,
                security_patch=patch
            )

            if run.submission_id != submission.id:
                print(f"Updating Run {run.id}: Submission {run.submission_id} -> {submission.id}")
                run.submission_id = submission.id
            
            # Update TestRun metadata if missing
            if not run.build_brand and brand:
                run.build_brand = brand
            if not run.build_model and model:
                run.build_model = model
            if not run.build_device and device:
                run.build_device = device
            if not run.security_patch and patch != "NoPatch":
                run.security_patch = patch
            
            # Migration: Update existing submission names to new format if still in default format
            if submission.name.startswith("Submission ") or " (Build: " in submission.name:
                s_brand = brand or "Unknown"
                s_model = model or "Device"
                s_device = device or "Unknown"
                s_patch = patch
                
                suffix_label = "Unknown"
                if m:
                    raw_suffix = m.group(4).lstrip('/')
                    suffix_label = raw_suffix.split('_')[0].split(':')[0]
                
                new_name = f"{s_brand} {s_model} ({s_device}) - {s_patch} (Build: {suffix_label})"
                if submission.name != new_name:
                    print(f"Renaming Submission {submission.id}: {submission.name} -> {new_name}")
                    submission.name = new_name
                    submission.brand = s_brand
                    submission.device = s_device
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
