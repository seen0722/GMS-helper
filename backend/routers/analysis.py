from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from backend.database.database import get_db, SessionLocal
from backend.database import models
from backend.analysis.clustering import ImprovedFailureClusterer
from backend.analysis.llm_client import get_llm_client
from typing import List, Dict, Any, Optional
import traceback

router = APIRouter()

from backend.services.analysis_service import AnalysisService

def run_analysis_task(run_id: int):
    # Wrapper for background task
    db = SessionLocal()
    try:
        AnalysisService.run_analysis_task(run_id, db)
    finally:
        db.close()



@router.post("/run/{run_id}")
async def trigger_analysis(run_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Check if run exists
    run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    # Set analysis status to 'analyzing'
    run.analysis_status = "analyzing"
    db.commit()
    
    # Run analysis in background
    print(f"Triggering analysis for run {run_id} in background")
    background_tasks.add_task(run_analysis_task, run_id)
    
    return {"message": "Analysis started in background"}

@router.get("/run/{run_id}/status")
def get_analysis_status(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return {"analysis_status": run.analysis_status or "pending"}

@router.get("/run/{run_id}/clusters")
def get_clusters(run_id: int, db: Session = Depends(get_db)):
    # Get all clusters associated with this run
    # This requires a join: TestRun -> TestCase -> FailureAnalysis -> FailureCluster
    clusters = db.query(models.FailureCluster).join(models.FailureAnalysis).join(models.TestCase).filter(
        models.TestCase.test_run_id == run_id
    ).distinct().all()
    
    # Get Redmine client if configured
    try:
        from backend.integrations.redmine_client import RedmineClient
        from backend.utils import encryption
        settings = db.query(models.Settings).first()
        redmine_client = None
        if settings and settings.redmine_url and settings.redmine_api_key:
            try:
                api_key = encryption.decrypt(settings.redmine_api_key)
                redmine_client = RedmineClient(settings.redmine_url, api_key)
            except:
                pass
    except:
        redmine_client = None
    
    # Enhance clusters with failure count for this run and Redmine status
    enhanced_clusters = []
    for cluster in clusters:
        count = db.query(models.TestCase).join(models.FailureAnalysis).filter(
            models.TestCase.test_run_id == run_id,
            models.FailureAnalysis.cluster_id == cluster.id
        ).count()
        
        # Convert to dict
        cluster_dict = {c.name: getattr(cluster, c.name) for c in cluster.__table__.columns}
        cluster_dict["failures_count"] = count
        
        # Get distinct module names
        modules = db.query(models.TestCase.module_name).join(models.FailureAnalysis).filter(
            models.TestCase.test_run_id == run_id,
            models.FailureAnalysis.cluster_id == cluster.id
        ).distinct().all()
        cluster_dict["module_names"] = [m[0] for m in modules]
        
        # Fetch Redmine issue status if linked
        if cluster.redmine_issue_id and redmine_client:
            try:
                issue = redmine_client.get_issue(cluster.redmine_issue_id)
                if issue:
                    if 'status' in issue:
                        cluster_dict["redmine_status"] = issue['status'].get('name', 'Unknown')
                        cluster_dict["redmine_status_id"] = issue['status'].get('id', 0)
                    
                    if 'assigned_to' in issue:
                        cluster_dict["redmine_assignee"] = issue['assigned_to'].get('name')
                        cluster_dict["redmine_assignee_id"] = issue['assigned_to'].get('id')
                else:
                    cluster_dict["redmine_status"] = None
                    cluster_dict["redmine_assignee"] = None
            except:
                cluster_dict["redmine_status"] = None
                cluster_dict["redmine_assignee"] = None
        else:
            cluster_dict["redmine_status"] = None
            cluster_dict["redmine_assignee"] = None
        
        # Resolve suggested assignee if not synced
        if not cluster_dict.get("redmine_assignee_id"):
            try:
                from backend.integrations.assignment_resolver import get_assignment_resolver
                resolver = get_assignment_resolver()
                # Use the first module to determine assignment
                module_for_resolution = cluster_dict["module_names"][0] if cluster_dict["module_names"] else None
                assignment = resolver.resolve_assignment(module_for_resolution)
                cluster_dict["suggested_assignee_id"] = assignment.get("user_id")
                cluster_dict["suggested_assignee_source"] = assignment.get("resolved_from")
            except Exception as e:
                print(f"Error resolving assignment for cluster {cluster.id}: {e}")
                cluster_dict["suggested_assignee_id"] = None
                cluster_dict["suggested_assignee_source"] = None
        
        enhanced_clusters.append(cluster_dict)
        
    return enhanced_clusters

@router.get("/cluster/{cluster_id}/failures")
def get_cluster_failures(cluster_id: int, db: Session = Depends(get_db)):
    # Get all failures associated with this cluster
    failures = db.query(models.TestCase).join(models.FailureAnalysis).filter(
        models.FailureAnalysis.cluster_id == cluster_id
    ).distinct().limit(50).all() # Limit to 50 for now
    return failures


@router.get("/submission/{submission_id}/clusters")
def get_submission_clusters(
    submission_id: int, 
    suite_filter: Optional[str] = Query(None), 
    db: Session = Depends(get_db)
):
    """
    Get aggregated clusters for a submission, optionally filtered by suite (CTS, GTS, etc.).
    """
    # 1. Fetch Submission to get context (target_fingerprint for GSI logic)
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    # 2. Identify relevant Test Runs
    runs_query = db.query(models.TestRun).filter(models.TestRun.submission_id == submission_id)
    all_runs = runs_query.all()
    
    target_run_ids = []
    
    if not suite_filter or suite_filter.lower() == 'all':
        target_run_ids = [r.id for r in all_runs]
    else:
        # Apply Suite Filtering Logic (matching logic in submissions.py)
        filter_upper = suite_filter.upper()
        
        for run in all_runs:
            run_suite_name = (run.test_suite_name or '').upper()
            
            # GSI Logic
            # 1. suite_plan is 'cts-on-gsi' (Strongest Signal)
            run_plan = (run.suite_plan or '').lower()
            is_gsi_plan = 'cts-on-gsi' in run_plan
            
            # 2. Fallbacks
            is_gsi_product = (run.build_product and 'gsi' in run.build_product.lower()) or \
                             (run.build_model and 'gsi' in run.build_model.lower())
            
            is_gsi = is_gsi_plan or is_gsi_product

            if filter_upper == 'CTS':
                # CTS tab should show standard CTS, exclude GSI usually? 
                # Or if user strictly wants "CTS" string match. 
                # Let's align with Dashboard logic: CTS Tab = CTS Suite & NOT GSI
                if 'CTS' in run_suite_name and not is_gsi:
                    target_run_ids.append(run.id)
            
            elif filter_upper == 'GSI' or filter_upper == 'CTSONGSI':
                # Matches GSI logic
                if 'CTS' in run_suite_name and is_gsi:
                     target_run_ids.append(run.id)
            
            else:
                # Standard substring match for GTS, VTS, STS, etc.
                if filter_upper in run_suite_name:
                    target_run_ids.append(run.id)

    if not target_run_ids:
        return []

    # 3. Fetch Clusters linked to these Runs
    # Join: Cluster <- Analysis <- TestCase
    clusters = db.query(models.FailureCluster).join(models.FailureAnalysis).join(models.TestCase).filter(
        models.TestCase.test_run_id.in_(target_run_ids)
    ).distinct().all()

    # Get Redmine Client (Optimization: Init once)
    try:
        from backend.integrations.redmine_client import RedmineClient
        from backend.utils import encryption
        settings = db.query(models.Settings).first()
        redmine_client = None
        if settings and settings.redmine_url and settings.redmine_api_key:
            try:
                api_key = encryption.decrypt(settings.redmine_api_key)
                redmine_client = RedmineClient(settings.redmine_url, api_key)
            except:
                pass
    except:
        redmine_client = None

    # 4. Enhance Clusters with Aggregated Stats
    enhanced_clusters = []
    
    # Pre-fetch resolution logic if needed
    try:
        from backend.integrations.assignment_resolver import get_assignment_resolver
        resolver = get_assignment_resolver()
    except:
        resolver = None

    for cluster in clusters:
        # Calculate failure count *scoped to the filtered runs*
        count = db.query(models.TestCase).join(models.FailureAnalysis).filter(
            models.TestCase.test_run_id.in_(target_run_ids),
            models.FailureAnalysis.cluster_id == cluster.id
        ).count()
        
        if count == 0:
            continue # Should not look happen given the main query, but safety check

        # Convert to dict
        cluster_dict = {c.name: getattr(cluster, c.name) for c in cluster.__table__.columns}
        cluster_dict["failures_count"] = count  # Aggregated count
        
        # Get module names (scoped)
        modules = db.query(models.TestCase.module_name).join(models.FailureAnalysis).filter(
            models.TestCase.test_run_id.in_(target_run_ids),
            models.FailureAnalysis.cluster_id == cluster.id
        ).distinct().all()
        cluster_dict["module_names"] = [m[0] for m in modules]
        
        # Redmine Info
        if cluster.redmine_issue_id and redmine_client:
            try:
                issue = redmine_client.get_issue(cluster.redmine_issue_id)
                if issue:
                    if 'status' in issue:
                        cluster_dict["redmine_status"] = issue['status'].get('name', 'Unknown')
                        cluster_dict["redmine_status_id"] = issue['status'].get('id', 0)
                    if 'assigned_to' in issue:
                        cluster_dict["redmine_assignee"] = issue['assigned_to'].get('name')
                        cluster_dict["redmine_assignee_id"] = issue['assigned_to'].get('id')
            except:
                pass
        
        # Suggested Assignment
        if not cluster_dict.get("redmine_assignee") and resolver:
            try:
                module_for_res = cluster_dict["module_names"][0] if cluster_dict["module_names"] else None
                assignment = resolver.resolve_assignment(module_for_res)
                
                # Only overwrite if resolver has a suggestion, otherwise keep AI suggestion or DB value
                if assignment.get("team_name"):
                    cluster_dict["suggested_assignment"] = assignment.get("team_name")
                
                if assignment.get("user_id"):
                    cluster_dict["suggested_assignee_id"] = assignment.get("user_id")
                
                if assignment.get("resolved_from"):
                    cluster_dict["suggested_assignee_source"] = assignment.get("resolved_from")
            except:
                pass

        enhanced_clusters.append(cluster_dict)

    # Sort: High Severity first, then by count desc
    def sort_key(c):
        sev_score = 3 if c.get('severity') == 'High' else (2 if c.get('severity') == 'Medium' else 1)
        return (-sev_score, -c.get('failures_count', 0))
    
    enhanced_clusters.sort(key=sort_key)
    
    return enhanced_clusters

def get_clusters_by_module(run_id: int, db: Session = Depends(get_db)):
    """
    Get clusters grouped by module for hierarchical UI display.
    PRD Phase 5: Hierarchical UI
    """
    # Get all test cases with their cluster info for this run
    results = db.query(
        models.TestCase.module_name,
        models.FailureCluster,
        models.FailureAnalysis
    ).join(
        models.FailureAnalysis, models.TestCase.id == models.FailureAnalysis.test_case_id
    ).join(
        models.FailureCluster, models.FailureAnalysis.cluster_id == models.FailureCluster.id
    ).filter(
        models.TestCase.test_run_id == run_id
    ).all()
    
    if not results:
        return {"modules": []}
    
    # Group by module
    module_data = {}
    cluster_failures = {}  # cluster_id -> count
    
    for module_name, cluster, analysis in results:
        # Track failures per cluster
        if cluster.id not in cluster_failures:
            cluster_failures[cluster.id] = 0
        cluster_failures[cluster.id] += 1
        
        # Initialize module if new
        if module_name not in module_data:
            module_data[module_name] = {
                "name": module_name,
                "total_failures": 0,
                "clusters": {},  # cluster_id -> cluster_info
            }
        
        module_data[module_name]["total_failures"] += 1
        
        # Add cluster to module if not already there
        if cluster.id not in module_data[module_name]["clusters"]:
            module_data[module_name]["clusters"][cluster.id] = {
                "id": cluster.id,
                "description": cluster.description,
                "severity": cluster.severity,
                "category": cluster.category,
                "ai_summary": cluster.ai_summary[:200] if cluster.ai_summary else None,
                "failures_in_module": 0
            }
        
        module_data[module_name]["clusters"][cluster.id]["failures_in_module"] += 1
    
    # Calculate priority and convert to list format
    modules_list = []
    for module_name, data in module_data.items():
        # Determine priority based on total failures and severity
        total = data["total_failures"]
        has_high_severity = any(c["severity"] == "High" for c in data["clusters"].values())
        
        if has_high_severity:
            priority = "P0"
        elif total > 15:
            priority = "P1"
        elif total >= 5:
            priority = "P2"
        else:
            priority = "P3"
        
        modules_list.append({
            "name": module_name,
            "total_failures": total,
            "priority": priority,
            "cluster_count": len(data["clusters"]),
            "clusters": list(data["clusters"].values())
        })
    
    # Sort by total failures descending
    modules_list.sort(key=lambda x: (-x["total_failures"], x["name"]))
    
    return {"modules": modules_list}
