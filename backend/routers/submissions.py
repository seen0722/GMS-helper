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
                # Calculate effective stats across all matching runs
                # Sort by time
                matching_runs.sort(key=lambda x: x.start_time)
                
                # Get all failures for these runs
                run_ids = [r.id for r in matching_runs]
                failures = db.query(models.TestCase).filter(models.TestCase.test_run_id.in_(run_ids)).all()
                
                # Group by case key
                case_history = {} # (mod, cls, mth) -> [fail_run_idx, ...]
                
                # Pre-calculate run ID to index map
                run_id_map = {r.id: i for i, r in enumerate(matching_runs)}
                
                for f in failures:
                    key = (f.module_name, f.class_name, f.method_name)
                    if key not in case_history:
                        case_history[key] = []
                    # Record that it failed in this run index
                    if f.test_run_id in run_id_map:
                         case_history[key].append(run_id_map[f.test_run_id])
                
                initial_failures = 0
                recovered_failures = 0
                remaining_failures = 0
                
                # Get latest run (for fallback passed/failed counts if no history logic needed, but we do need it)
                latest = matching_runs[-1]
                
                if not failures and len(matching_runs) == 1:
                     # Single run, no failures in DB -> All passed? 
                     # Wait, TestCase table only stores failures.
                     # So if no entries, it's 0 failures.
                     pass
                
                for key, fail_indices in case_history.items():
                    # Sort indices
                    fail_indices.sort()
                    
                    # Initial failure = failed in first run (index 0)
                    if 0 in fail_indices:
                        initial_failures += 1
                        
                    # Remaining failure = failed in last run (index len-1)
                    if (len(matching_runs) - 1) in fail_indices:
                        remaining_failures += 1
                    else:
                        # If it failed at some point but NOT in the last run, it's recovered
                        # (assuming implicit pass in last run)
                        recovered_failures += 1
                
                # If single run, initial == remaining
                if len(matching_runs) == 1:
                    initial_failures = remaining_failures
                    recovered_failures = 0
                
                # Total Passed = Total Tests (from latest) - Remaining Failures
                # Use latest run's total tests as approximation
                total_tests = latest.total_tests or 0
                passed_tests = max(0, total_tests - remaining_failures)

                suite_summary[suite_cfg.name] = {
                    "status": "fail" if remaining_failures > 0 else "pass",
                    "failed": remaining_failures,
                    "passed": passed_tests,
                    "initial_failed": initial_failures,
                    "recovered": recovered_failures,
                    "run_count": len(matching_runs)
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
    


class MergeReportItem(BaseModel):
    module_name: str
    test_class: str
    test_method: str
    initial_run_id: int
    final_run_id: int
    is_recovered: bool
    status_history: List[str] # ["fail", "fail", "pass"]

class SuiteMergeDetail(BaseModel):
    suite_name: str
    run_ids: List[int]
    summary: dict # { "initial": 10, "recovered": 8, "remaining": 2 }
    items: List[MergeReportItem]

class MergeReportSummary(BaseModel):
    submission_id: int
    total_initial_failures: int
    total_recovered: int
    remaining_failures: int
    suites: List[SuiteMergeDetail]
    
@router.get("/{submission_id}/merge_report")
def get_submission_merge_report(submission_id: int, db: Session = Depends(get_db)):
    """Get a consolidated report of failures across all runs in a submission."""
    from backend.services.merge_service import MergeService
    
    report_data = MergeService.get_merge_report(db, submission_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail="Submission not found or no runs")
        
    # Transform to Pydantic model format (convert internal dict objects to dicts matching MergeReportItem)
    # The MergeService returns internal dicts which are richer, we need to adapt if needed
    # But checking the previous Pydantic model, it expects simple fields.
    
    suites_response = []
    
    for suite_data in report_data["suites"]:
        items_response = []
        for item in suite_data["items"]:
            items_response.append({
                "module_name": item["module_name"],
                "test_class": item["test_class"],
                "test_method": item["test_method"],
                "initial_run_id": item["initial_run_id"],
                "final_run_id": item["final_run_id"],
                "is_recovered": item["is_recovered"],
                "status_history": item["status_history"]
            })
            
        suites_response.append({
            "suite_name": suite_data["suite_name"],
            "run_ids": suite_data["run_ids"],
            "summary": suite_data["summary"],
            "items": items_response
        })
    
    return {
        "submission_id": report_data["submission_id"],
        "total_initial_failures": report_data["total_initial_failures"],
        "total_recovered": report_data["total_recovered"],
        "remaining_failures": report_data["remaining_failures"],
        "suites": suites_response
    }

