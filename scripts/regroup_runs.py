import sys
import os
import re
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.database import SessionLocal
from backend.database import models
from sqlalchemy import desc

def regroup():
    db = SessionLocal()
    try:
        # 1. Fetch all runs ordered by ID (chronological)
        runs = db.query(models.TestRun).order_by(models.TestRun.id).all()
        
        # Track updated submissions to avoid duplicate logic within this script
        # Submissions created/matched during this run
        # Map: GroupingKey -> SubmissionID
        # GroupingKey: fingerprint (for exact) OR (prefix, suffix) (for GSI/VTS)
        match_cache = {}

        print(f"Repairing {len(runs)} runs...")

        for run in runs:
            old_sub_id = run.submission_id
            fingerprint = run.device_fingerprint
            
            if not fingerprint or fingerprint == "Pending...":
                continue

            # Determine if this is a system-replace run (GSI/VTS)
            is_system_replace = (
                (run.test_suite_name == "CTS" and run.suite_plan and "cts-on-gsi" in run.suite_plan.lower()) or
                (run.test_suite_name == "VTS" and run.suite_plan and "vts" in run.suite_plan.lower())
            )

            matched_sub = None
            
            # Use granular pattern for matching
            fp_pattern = re.compile(r"^([^:]+):([^/]+)/([^/]+)(/.+)$")
            match = fp_pattern.match(fingerprint)
            
            if is_system_replace and match:
                prefix = match.group(1)
                suffix = match.group(4)
                key = f"SR:{prefix}:{suffix}"
                
                # Check cache
                if key in match_cache:
                    matched_sub = db.query(models.Submission).get(match_cache[key])
                else:
                    # Look for candidate in DB
                    cand = db.query(models.Submission).filter(
                        models.Submission.target_fingerprint.like(f"{prefix}:%")
                    ).order_by(desc(models.Submission.updated_at)).all()
                    
                    for c in cand:
                        c_match = fp_pattern.match(c.target_fingerprint)
                        if c_match and c_match.group(1) == prefix and c_match.group(4) == suffix:
                            matched_sub = c
                            match_cache[key] = c.id
                            break
            else:
                # Standard Exact Match
                key = f"EX:{fingerprint}"
                if key in match_cache:
                    matched_sub = db.query(models.Submission).get(match_cache[key])
                else:
                    matched_sub = db.query(models.Submission).filter(
                        models.Submission.target_fingerprint == fingerprint
                    ).order_by(desc(models.Submission.updated_at)).first()
                    if matched_sub:
                        match_cache[key] = matched_sub.id

            if not matched_sub:
                # Create new submission if no match found
                prod = run.build_product or "Unknown"
                sub_name = f"Submission {prod} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
                
                matched_sub = models.Submission(
                    name=sub_name,
                    target_fingerprint=fingerprint,
                    status="analyzing",
                    gms_version=run.android_version,
                    product=run.build_product
                )
                db.add(matched_sub)
                db.flush()
                match_cache[key] = matched_sub.id
                print(f"Created new Submission {matched_sub.id} for key {key}")

            if run.submission_id != matched_sub.id:
                print(f"Updating Run {run.id}: Submission {run.submission_id} -> {matched_sub.id}")
                run.submission_id = matched_sub.id
        
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
