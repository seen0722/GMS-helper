from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import List, Optional
from datetime import datetime
from backend.database.database import get_db
from backend.database import models

from pydantic import BaseModel

router = APIRouter()

class SubmissionUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None

class MoveRunsRequest(BaseModel):
    run_ids: List[int]
    target_submission_id: int

@router.get("/")
def get_submissions(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """List all submissions with suite status summary."""
    submissions = db.query(models.Submission).order_by(desc(models.Submission.updated_at)).offset(skip).limit(limit).all()
    
    # Fetch configured suites
    suites_config = db.query(models.TestSuiteConfig).filter(models.TestSuiteConfig.is_required == 1).order_by(asc(models.TestSuiteConfig.sort_order)).all()
    
    results = []
    for sub in submissions:
        # Basic stats
        run_count = len(sub.test_runs)
        
        # Calculate suite status summary
        suite_summary = {}
        
        # Helper to match suite (handling CTS vs CTSonGSI)
        def match_suite(run, config):
            name = (run.test_suite_name or '').upper()
            
            if config.match_rule == 'GSI':
                return 'CTS' in name and run.device_fingerprint != sub.target_fingerprint
            
            if config.name == 'CTS': # Standard CTS (exclude GSI)
                # If rule is Standard but name is CTS, exclude GSI
                is_gsi = run.device_fingerprint != sub.target_fingerprint
                return 'CTS' in name and not is_gsi
            
            return config.name in name

        for suite_cfg in suites_config:
            # Find runs matching this suite type
            matching_runs = [r for r in sub.test_runs if match_suite(r, suite_cfg)]
            
            if not matching_runs:
                suite_summary[suite_cfg.name] = {"status": "missing", "failed": 0, "passed": 0}
            else:
                # Get latest run for this suite
                latest = matching_runs[0]
                has_fails = (latest.failed_tests or 0) > 0
                suite_summary[suite_cfg.name] = {
                    "status": "fail" if has_fails else "pass",
                    "failed": latest.failed_tests or 0,
                    "passed": latest.passed_tests or 0
                }
        
        results.append({
            "id": sub.id,
            "name": sub.name,
            "status": sub.status,
            "gms_version": sub.gms_version,
            "target_fingerprint": sub.target_fingerprint,
            "created_at": sub.created_at,
            "updated_at": sub.updated_at,
            "run_count": run_count,
            "suite_summary": suite_summary
        })
    
    # Calculate total count for pagination
    total_count = db.query(models.Submission).count()

    return {
        "items": results,
        "total": total_count,
        "page": (skip // limit) + 1,
        "size": limit
    }

@router.get("/{submission_id}")
def get_submission_details(submission_id: int, db: Session = Depends(get_db)):
    """Get submission details including associated test runs and intelligence warnings."""
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Fetch configured suites
    suites_config = db.query(models.TestSuiteConfig).filter(models.TestSuiteConfig.is_required == 1).order_by(asc(models.TestSuiteConfig.sort_order)).all()
    
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
             "device_fingerprint": run.device_fingerprint,
             "device_abi": run.build_abis, # Use build_abis as device_abi
             "security_patch": run.security_patch
         })
    
    # --- Phase 3: Intelligence Warnings ---
    warnings = []
    
    # helper to check if run matches suite type (handling CTS vs CTSonGSI)
    def match_suite(run, config):
        name = (run.test_suite_name or '').upper()
        
        if config.match_rule == 'GSI':
            # It matches if name is CTS AND fingerprint differs from target
            # Note: We assume sub.target_fingerprint is the Vendor Build
            return 'CTS' in name and run.device_fingerprint != sub.target_fingerprint
            
        if config.name == 'CTS':
            # Matches CTS only if fingerprint MATCHES target (or we strictly exclude GSI)
            is_gsi = run.device_fingerprint != sub.target_fingerprint
            return 'CTS' in name and not is_gsi
            
        return config.name in name

    # 1. Missing Suite Detection
    for suite_cfg in suites_config:
        has_suite = any(match_suite(r, suite_cfg) for r in runs)
        if not has_suite:
            warnings.append({
                "type": "missing_suite",
                "severity": "warning",
                "message": f"{suite_cfg.name} results not uploaded yet",
                "suite": suite_cfg.name
            })
    
    # 2. Cross-Suite Verification (only if we have multiple runs)
    if len(runs) >= 2:
        # Check fingerprint consistency (Exclude GSI from consistency check?)
        # GSI runs WILL have different fingerprint, so we should only check 
        # consistency among NON-GSI runs, or group them.
        
        # Filter out GSI runs for main verification
        standard_runs = [r for r in runs if r.device_fingerprint == sub.target_fingerprint]
        
        if len(standard_runs) >= 2:
            fingerprints = set(r.device_fingerprint for r in standard_runs if r.device_fingerprint)
            if len(fingerprints) > 1:
                warnings.append({
                    "type": "fingerprint_mismatch",
                    "severity": "error",
                    "message": f"Device fingerprint mismatch across runs: {', '.join(fingerprints)}"
                })
            
            # Check ABI consistency
            abis = set(r.build_abis for r in standard_runs if r.build_abis)
            if len(abis) > 1:
                warnings.append({
                    "type": "abi_mismatch",
                    "severity": "error",
                    "message": f"Device ABI mismatch across runs: {', '.join(abis)}"
                })
        
        # Check security patch consistency
        patches = set(r.security_patch for r in runs if r.security_patch)
        if len(patches) > 1:
            warnings.append({
                "type": "security_patch_mismatch",
                "severity": "error",
                "message": f"Security patch level inconsistent: {', '.join(patches)}"
            })
    
    return {
        "id": sub.id,
        "name": sub.name,
        "status": sub.status,
        "gms_version": sub.gms_version,
        "target_fingerprint": sub.target_fingerprint,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
        "test_runs": run_list,
        "warnings": warnings
    }

@router.delete("/{submission_id}")
def delete_submission(submission_id: int, db: Session = Depends(get_db)):
    """Delete a submission and all associated runs."""
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    db.delete(sub)
    db.commit()
    
    return {"message": "Submission deleted successfully"}

@router.patch("/{submission_id}")
def update_submission(submission_id: int, update: SubmissionUpdate, db: Session = Depends(get_db)):
    """Update a submission's name or status."""
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if update.name is not None:
        sub.name = update.name
    if update.status is not None:
        sub.status = update.status
        
    sub.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sub)
    

    return {
        "id": sub.id,
        "name": sub.name,
        "status": sub.status,
        "updated_at": sub.updated_at
    }

@router.post("/runs/move")
def move_runs(request: MoveRunsRequest, db: Session = Depends(get_db)):
    """Move test runs to a different submission."""
    # Validate target submission
    target_sub = db.query(models.Submission).filter(models.Submission.id == request.target_submission_id).first()
    if not target_sub:
        raise HTTPException(status_code=404, detail="Target submission not found")
    
    # Update runs
    moved_count = 0
    for run_id in request.run_ids:
        run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
        if run:
            run.submission_id = target_sub.id
            moved_count += 1
            
    # Update timestamps
    target_sub.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "message": f"Successfully moved {moved_count} runs", 
        "target_submission": target_sub.name,
        "moved_count": moved_count
    }
