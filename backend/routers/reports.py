from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from backend.database.database import get_db
from backend.database import models
from typing import List, Optional
import json
from backend.analysis.llm_client import get_llm_client # Import LLM Factory

router = APIRouter()


from backend.services.merge_service import MergeService

def _aggregate_submission_failures(db: Session, submission_id: int) -> List[dict]:
    """
    Aggregate failures for a submission using the shared MergeService to ensure
    consistent logic (handling implicit passes correctly).
    """
    report = MergeService.get_merge_report(db, submission_id)
    if not report:
        return []
        
    persistent_failures = []
    
    # Iterate through suites and items to find remaining failures
    for suite in report["suites"]:
        for item in suite["items"]:
            if not item["is_recovered"]:
                # This is a persistent failure
                # MergeService returns 'failure_details' in the item
                f_details = item.get("failure_details") 
                # Note: f_details might be a SQLModel object or dict depending on MergeService impl
                
                module = item["module_name"]
                error = getattr(f_details, "error_message", "Unknown Error")
                stack = getattr(f_details, "stack_trace", "") or ""
                test_name = f"{item['test_class']}#{item['test_method']}"
                
                persistent_failures.append({
                    'test': test_name,
                    'module': module,
                    'error': error,
                    'stack_trace': stack[:500]
                })
                
    return persistent_failures



@router.post("/submissions/{submission_id}/analyze")
def analyze_submission(submission_id: int, db: Session = Depends(get_db)):
    """
    Trigger AI analysis for the entire submission.
    Aggregates persistent failures and asks LLM for a high-level report.
    """
    # 1. Check submission
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    # 2. Aggregate Failures
    failures = _aggregate_submission_failures(db, submission_id)
    
    if not failures:
        # No failures!
        result = {
            "executive_summary": "Excellent quality! No persistent failures detected in this submission.",
            "top_risks": [],
            "recommendations": ["Proceed to release"],
            "severity_score": 0
        }
        sub.analysis_result = json.dumps(result)
        db.commit()
        return result
        
    # 3. Format Prompt
    # 3. Intelligent Clustering (Smart Grouping)
    # Group by (Module, Error Signature) to identify systemic patterns
    clusters = {}
    for f in failures:
        # Create a signature based on Module + Error Message (first 100 chars)
        # We ignore the specific test case name for grouping, as we want to find the ROOT CAUSE
        sig = f"{f['module']}::{f['error'][:100]}" 
        if sig not in clusters:
            clusters[sig] = {
                'count': 0,
                'module': f['module'],
                'error': f['error'],
                'example_stack': f['stack_trace'],
                'example_test': f['test']
            }
        clusters[sig]['count'] += 1

    # Sort clusters by impact (count)
    sorted_clusters = sorted(clusters.values(), key=lambda x: x['count'], reverse=True)

    # Format Prompt with Cluster Data
    prompt_text = f"Analyzed {len(failures)} Persistent Failures. Grouped into {len(sorted_clusters)} distinct patterns:\n\n"
    
    for i, c in enumerate(sorted_clusters[:10]): # Top 10 Patterns
        prompt_text += (
            f"Pattern #{i+1} (Count: {c['count']}):\n"
            f"Module: {c['module']}\n"
            f"Error: {c['error']}\n"
            f"Example Test: {c['example_test']}\n"
            f"Stack Snippet: {c['example_stack']}\n\n"
        )
        
    if len(sorted_clusters) > 10:
        prompt_text += f"\n... and {len(sorted_clusters) - 10} minor failure patterns."
        
    # 4. Call LLM
    try:
        client = get_llm_client()
        analysis = client.analyze_submission(prompt_text)
        
        # 5. Save Result
        sub.analysis_result = json.dumps(analysis)
        db.commit()
        
        return analysis
    except Exception as e:
        print(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/submissions/{submission_id}/analysis")
def get_submission_analysis(submission_id: int, db: Session = Depends(get_db)):
    """Get stored analysis result."""
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if not sub.analysis_result:
        return None
        
    return json.loads(sub.analysis_result)

@router.get("/runs")
def get_test_runs(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    runs = db.query(models.TestRun).options(joinedload(models.TestRun.submission)).order_by(models.TestRun.start_time.desc()).offset(skip).limit(limit).all()
    
    # Enhance runs with cluster count
    enhanced_runs = []
    for run in runs:
        cluster_count = db.query(models.FailureCluster).join(models.FailureAnalysis).join(models.TestCase).filter(
            models.TestCase.test_run_id == run.id
        ).distinct().count()
        
        # Convert to dict to add extra field
        run_dict = {c.name: getattr(run, c.name) for c in run.__table__.columns}
        run_dict["cluster_count"] = cluster_count
        # Add submission target fingerprint for GSI detection
        run_dict["target_fingerprint"] = run.submission.target_fingerprint if run.submission else None
        
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
    run = db.query(models.TestRun).options(joinedload(models.TestRun.submission)).filter(models.TestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    # Convert to dict/schema to include submission target fingerprint
    # We can rely on Pydantic `from_orm` if we had schemas, but simple dict works for now to match other endpoints approach or flexible return
    # But wait, other tools might expect raw fields.
    # Let's attach it as an extra attribute if possible, or return dict.
    
    run_dict = {c.name: getattr(run, c.name) for c in run.__table__.columns}
    run_dict["target_fingerprint"] = run.submission.target_fingerprint if run.submission else None
    
    return run_dict

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

