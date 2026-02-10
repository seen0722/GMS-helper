from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import List, Optional
from datetime import datetime
import json
from backend.database.database import get_db
from backend.database import models
from backend.services.suite_service import SuiteService
from backend.services.merge_service import MergeService
from backend.services.analysis_service import AnalysisService

from pydantic import BaseModel

router = APIRouter()

class SubmissionUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None

class MoveRunsRequest(BaseModel):
    run_ids: List[int]
    target_submission_id: Optional[int] = None # None = Create New

class LockSubmissionRequest(BaseModel):
    is_locked: bool

@router.post("/{submission_id}/lock")
def toggle_lock(submission_id: int, req: LockSubmissionRequest, db: Session = Depends(get_db)):
    """Lock or Unlock a submission."""
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    sub.is_locked = req.is_locked
    if req.is_locked:
        sub.status = "published" # Auto-publish on lock? Or keep separate? Let's say Locked implies Ready/Protected.
    else:
        # If unlocking, maybe revert to analyzing?
        pass 
        
    db.commit()
    return {"message": f"Submission {'locked' if req.is_locked else 'unlocked'}", "is_locked": sub.is_locked}

@router.post("/move-runs")
def move_runs(req: MoveRunsRequest, db: Session = Depends(get_db)):
    """Move runs to another submission or a new one."""
    runs = db.query(models.TestRun).filter(models.TestRun.id.in_(req.run_ids)).all()
    if not runs:
        raise HTTPException(status_code=404, detail="No runs found")
        
    source_sub_id = runs[0].submission_id
    
    target_sub = None
    if req.target_submission_id:
        target_sub = db.query(models.Submission).filter(models.Submission.id == req.target_submission_id).first()
        if not target_sub:
            raise HTTPException(status_code=404, detail="Target submission not found")
    else:
        # Create New Submission based on the first run's metadata
        first_run = runs[0]
        new_name = f"Submission {first_run.build_product or 'New'} - Split {datetime.utcnow().strftime('%H:%M')}"
        target_sub = models.Submission(
            name=new_name,
            target_fingerprint=first_run.device_fingerprint,
            product=first_run.build_product,
            status="analyzing",
            gms_version=first_run.android_version
        )
        db.add(target_sub)
        db.flush()
        
    # Move runs
    for r in runs:
        r.submission_id = target_sub.id
        
    db.commit()
    
    return {"message": f"Moved {len(runs)} runs to Submission {target_sub.id}", "target_submission_id": target_sub.id}

@router.get("/products")
def get_products(db: Session = Depends(get_db)):
    """Get list of unique products for filtering."""
    # distinct products
    products = db.query(models.Submission.product).distinct().all()
    # Flatten list of tuples and remove None/Unknown if desired, or keep them
    # Filter out None
    product_list = sorted([p[0] for p in products if p[0]])
    return product_list

@router.get("/")
def get_submissions(skip: int = 0, limit: int = 20, product_filter: Optional[str] = None, db: Session = Depends(get_db)):
    """List all submissions with suite status summary."""
    query = db.query(models.Submission).order_by(desc(models.Submission.updated_at))
    
    if product_filter and product_filter != "All Products":
        query = query.filter(models.Submission.product == product_filter)
        
    submissions = query.offset(skip).limit(limit).all()
    
    # Fetch configured suites
    suites_config = db.query(models.TestSuiteConfig).order_by(asc(models.TestSuiteConfig.sort_order)).all()
    
    results = []
    for sub in submissions:
        # Basic stats
        run_count = len(sub.test_runs)
        
        # Calculate suite status summary
        suite_summary = {}
        
        for suite_cfg in suites_config:
            # Find runs matching this suite type
            matching_runs = [r for r in sub.test_runs if SuiteService.match_suite(r, suite_cfg, sub.target_fingerprint)]
            
            if not matching_runs:
                suite_summary[suite_cfg.name] = {"status": "missing", "failed": 0, "passed": 0}
            else:
                summary_data = MergeService.calculate_suite_summary(db, matching_runs)
                
                # Robust Pass Rate Calculation (Backend side)
                total = summary_data["total_tests"]
                failed = summary_data["remaining"]
                passed = total - failed
                
                suite_summary[suite_cfg.name] = {
                    "status": "fail" if failed > 0 else "pass",
                    "failed": failed,
                    "passed": passed,
                    "initial_failed": summary_data["initial"],
                    "recovered": summary_data["recovered"],
                    "run_count": len(matching_runs),
                    "is_merged": len(matching_runs) > 1,
                    "latest_run_id": matching_runs[-1].id,
                    "run_ids": [r.id for r in matching_runs]
                }

        results.append({
            "id": sub.id,
            "name": sub.name,
            "status": sub.status,
            "gms_version": sub.gms_version,
            "target_fingerprint": sub.target_fingerprint,
            "brand": sub.brand,
            "product": sub.product,
            "device": sub.device,
            "created_at": sub.created_at,
            "updated_at": sub.updated_at,
            "run_count": run_count,
            "suite_summary": suite_summary,
            "cluster_count": len(json.loads(sub.analysis_result).get("analyzed_clusters", [])) if sub.analysis_result else 0
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
    suites_config = db.query(models.TestSuiteConfig).order_by(asc(models.TestSuiteConfig.sort_order)).all()
    
    # Get associated runs
    runs = db.query(models.TestRun).filter(
        models.TestRun.submission_id == submission_id
    ).order_by(desc(models.TestRun.start_time)).all()
    
    run_list = []
    for run in runs:
         run_list.append({
             "id": run.id,
             "test_suite_name": run.test_suite_name,
             "suite_plan": run.suite_plan,  # Added suite_plan
             "start_time": run.start_time,
             "status": run.status,
             "analysis_status": run.analysis_status,
             "passed_tests": run.passed_tests,
             "failed_tests": run.failed_tests,
             "device_fingerprint": run.device_fingerprint,
             "device_product": run.build_product,
             "device_model": run.build_model,
             "device_abi": run.build_abis, # Use build_abis as device_abi
             "security_patch": run.security_patch,
             "test_cases": [
                 {
                     "module_name": tc.module_name,
                     "class_name": tc.class_name,
                     "method_name": tc.method_name,
                     "status": tc.status,
                     "stack_trace": tc.stack_trace,
                     "error_message": tc.error_message
                 } for tc in run.test_cases
             ]
         })
    
    # --- Calculate Suite Summary (Optimistic Merge) ---
    suite_summary = {}

    for suite_cfg in suites_config:
        matching_runs = [r for r in runs if SuiteService.match_suite(r, suite_cfg, sub.target_fingerprint)]
        
        if not matching_runs:
            suite_summary[suite_cfg.name] = {"status": "missing", "failed": 0, "passed": 0}
        else:
            summary_data = MergeService.calculate_suite_summary(db, matching_runs)
            
            suite_summary[suite_cfg.name] = {
                "status": "fail" if summary_data["remaining"] > 0 else "pass",
                "failed": summary_data["remaining"],
                "passed": summary_data["total_tests"] - summary_data["remaining"],
                "initial_failed": summary_data["initial"],
                "recovered": summary_data["recovered"],
                "run_count": len(matching_runs),
                "is_merged": len(matching_runs) > 1,
                "latest_run_id": matching_runs[-1].id,
                "run_ids": [r.id for r in matching_runs]
            }

    # --- Phase 3: Intelligence Warnings ---
    warnings = []
    
    # helper to check if run matches suite type (handling CTS vs CTSonGSI)

    # 1. Missing Suite Detection
    for suite_cfg in suites_config:
        has_suite = any(SuiteService.match_suite(r, suite_cfg, sub.target_fingerprint) for r in runs)
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
        "warnings": warnings,
        "suite_summary": suite_summary
    }

@router.delete("/{submission_id}")
def delete_submission(submission_id: int, db: Session = Depends(get_db)):
    """Delete a submission and all associated runs."""
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    db.delete(sub)
    db.commit()
    
    # Auto-cleanup orphan failure clusters
    AnalysisService.cleanup_orphan_clusters(db)
    
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
    
    # Clustering Logic for Triage View
    clusters_response = []
    
    # 1. Collect all persistent failures across all suites
    persistent_items = []
    for suite in suites_response:
        for item in suite["items"]:
            if not item["is_recovered"]:
                f_detail = item.get("failure_details")
                err_msg = ""
                stack = ""
                
                if f_detail:
                    if isinstance(f_detail, dict):
                        err_msg = f_detail.get("error_message", "")
                        stack = f_detail.get("stack_trace", "")
                    else:
                        err_msg = getattr(f_detail, "error_message", "")
                        stack = getattr(f_detail, "stack_trace", "")
                
                # Adapter for Clusterer
                persistent_items.append({
                    "id": f"{item['module_name']}::{item['test_class']}#{item['test_method']}", # Pseudo ID
                    "module_name": item["module_name"],
                    "class_name": item["test_class"],
                    "method_name": item["test_method"],
                    "error_message": err_msg or "",
                    "stack_trace": stack or "",
                    "original_item": item # Keep reference
                })
    
    if persistent_items:
        try:
            from backend.analysis.clustering import ImprovedFailureClusterer
            print(f"DEBUG: Found {len(persistent_items)} persistent items for clustering")
            clusterer = ImprovedFailureClusterer(min_cluster_size=2) # Low threshold for demo
            
            # Format for clusterer
            cluster_input = [{
                'module_name': p['module_name'],
                'class_name': p['class_name'],
                'method_name': p['method_name'],
                'stack_trace': p['stack_trace'],
                'error_message': p['error_message']
            } for p in persistent_items]
            
            labels, _ = clusterer.cluster_failures(cluster_input)
            print(f"DEBUG: Clustering labels: {labels}")
            
            # Group by label
            grouped = {}
            for idx, label in enumerate(labels):
                if label not in grouped:
                    grouped[label] = []
                grouped[label].append(persistent_items[idx])
            
            # ... (rest of the logic)

                
            # Try to match with AI Analysis Result if available
            ai_clusters = []
            submission_obj = report_data.get("submission")
            if submission_obj and submission_obj.analysis_result:
                try:
                    import json
                    analysis = json.loads(submission_obj.analysis_result)
                    ai_clusters = analysis.get("analyzed_clusters", [])
                except:
                    pass
            
            # Format Output
            for label, items in grouped.items():
                rep = items[0]
                
                # Heuristic Title
                title = f"Cluster {label}: {rep['module_name']} - {rep['error_message'][:50]}"
                
                # Try to find matching AI analysis
                # Simple logic: If AI cluster count matches or module matches
                matched_ai = None
                for ac in ai_clusters:
                    # weak matching
                   if ac.get('count') == len(items) and ac.get('redmine_component', '').lower() in rep['module_name'].lower():
                       matched_ai = ac
                       break
                
                category = "Uncategorized"
                severity = "Medium"
                root_cause = "Analysis Pending"
                
                if matched_ai:
                    title = f"{matched_ai.get('pattern_name', title)}"
                    category = matched_ai.get('category', 'Uncategorized')
                    severity = "High" # AI usually reports high risks
                    root_cause = matched_ai.get('root_cause', root_cause)
                else:
                    # Fallback Category Map
                    from backend.analysis.categories import get_category_for_module
                    category = get_category_for_module(rep['module_name'])
                
                clusters_response.append({
                    "id": int(label) if label >= 0 else 9999 + abs(int(label)), # Handle -1 noise
                    "title": title,
                    "failures_count": len(items),
                    "severity": severity,
                    "category": category,
                    "root_cause": root_cause,
                    "module_names": list(set(i['module_name'] for i in items)),
                    "items": [i['original_item'] for i in items]
                })
                
        except Exception as e:
            print(f"Clustering failed in merge report: {e}")
            # Fallback: One big cluster? Or empty.
            clusters_response.append({
                "id": -1,
                "title": f"Clustering Error: {str(e)}",
                "failures_count": 0,
                "severity": "Low",
                "category": "Error",
                "root_cause": str(e),
                "module_names": [],
                "items": []
            })
            pass

    return {
        "submission_id": report_data["submission_id"],
        "total_initial_failures": report_data["total_initial_failures"],
        "total_recovered": report_data["total_recovered"],
        "remaining_failures": report_data["remaining_failures"],
        "suites": suites_response,
        "clusters": clusters_response
    }

