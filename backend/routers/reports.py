from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from backend.database.database import get_db
from backend.database import models
from typing import List, Optional

router = APIRouter()

@router.get("/runs")
def get_test_runs(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    runs = db.query(models.TestRun).order_by(models.TestRun.start_time.desc()).offset(skip).limit(limit).all()
    
    # Enhance runs with cluster count
    enhanced_runs = []
    for run in runs:
        cluster_count = db.query(models.FailureCluster).join(models.FailureAnalysis).join(models.TestCase).filter(
            models.TestCase.test_run_id == run.id
        ).distinct().count()
        
        # Convert to dict to add extra field
        run_dict = {c.name: getattr(run, c.name) for c in run.__table__.columns}
        run_dict["cluster_count"] = cluster_count
        enhanced_runs.append(run_dict)
        
    return enhanced_runs

@router.get("/runs/{run_id}/stats")
def get_run_stats(run_id: int, db: Session = Depends(get_db)):
    """Get detailed module and test statistics for a test run."""
    
    # Get run with cached statistics
    run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    return {
        "xml_modules_done": run.xml_modules_done or 0,
        "xml_modules_total": run.xml_modules_total or 0,
        "total_modules": run.total_modules or 0,
        "passed_modules": run.passed_modules or 0,
        "failed_modules": run.failed_modules or 0,
        "total_tests": run.total_tests,
        "passed_tests": run.passed_tests,
        "failed_tests": run.failed_tests,
        "ignored_tests": run.ignored_tests
    }


@router.get("/runs/{run_id}")
def get_test_run_details(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run

@router.get("/runs/{run_id}/failures")
def get_run_failures(run_id: int, db: Session = Depends(get_db)):
    failures = db.query(models.TestCase).options(
        joinedload(models.TestCase.failure_analysis).joinedload(models.FailureAnalysis.cluster)
    ).filter(
        models.TestCase.test_run_id == run_id,
        models.TestCase.status == "fail"
    ).all()
    return failures

@router.get("/test-cases/{test_case_id}")
def get_test_case_details(test_case_id: int, db: Session = Depends(get_db)):
    """Get details for a specific test case."""
    test_case = db.query(models.TestCase).options(
        joinedload(models.TestCase.failure_analysis).joinedload(models.FailureAnalysis.cluster)
    ).filter(models.TestCase.id == test_case_id).first()
    
    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")
        
    return test_case

@router.delete("/runs/{run_id}")
def delete_test_run(run_id: int, db: Session = Depends(get_db)):
    """Delete a test run and all associated test cases."""
    run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    # Delete the run (cascade will delete associated test cases)
    db.delete(run)
    db.commit()
    
    # Ensure session is refreshed before checking for orphans
    db.expunge_all()
    
    # Cleanup orphaned clusters (clusters with no analysis records)
    # Since we added cascade delete to TestCase -> FailureAnalysis, 
    # deleting the run deletes test cases, which deletes failure analyses.
    # Now we check for clusters that have no analyses left.
    orphaned_clusters = db.query(models.FailureCluster).filter(~models.FailureCluster.analyses.any()).all()
    
    if orphaned_clusters:
        print(f"Deleting {len(orphaned_clusters)} orphaned clusters")
        for cluster in orphaned_clusters:
            print(f"  - Deleting cluster ID {cluster.id} (Redmine: {cluster.redmine_issue_id})")
            db.delete(cluster)
        db.commit()
    
    
    return {"message": "Test run deleted successfully", "run_id": run_id}

