from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
from backend.database.database import get_db
from backend.database import models

router = APIRouter()

@router.get("/")
def get_submissions(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """List all submissions."""
    submissions = db.query(models.Submission).order_by(desc(models.Submission.updated_at)).offset(skip).limit(limit).all()
    
    # Enhance specific counts? Or just return raw
    results = []
    for sub in submissions:
        # Basic stats
        run_count = len(sub.test_runs)
        results.append({
            "id": sub.id,
            "name": sub.name,
            "status": sub.status,
            "gms_version": sub.gms_version,
            "target_fingerprint": sub.target_fingerprint,
            "created_at": sub.created_at,
            "updated_at": sub.updated_at,
            "run_count": run_count
        })
    return results

@router.get("/{submission_id}")
def get_submission_details(submission_id: int, db: Session = Depends(get_db)):
    """Get submission details including associated test runs."""
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Get associated runs
    runs = db.query(models.TestRun).filter(
        models.TestRun.submission_id == submission_id
    ).order_by(desc(models.TestRun.start_time)).all()
    
    run_list = []
    for run in runs:
         run_list.append({
             "id": run.id,
             "test_suite_name": run.test_suite_name,
             "start_time": run.start_time,
             "status": run.status,
             "passed_tests": run.passed_tests,
             "failed_tests": run.failed_tests,
             "device_fingerprint": run.device_fingerprint
         })

    return {
        "id": sub.id,
        "name": sub.name,
        "status": sub.status,
        "gms_version": sub.gms_version,
        "target_fingerprint": sub.target_fingerprint,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
        "test_runs": run_list
    }
