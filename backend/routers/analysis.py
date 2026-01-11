from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database import models
from backend.analysis.clustering import ImprovedFailureClusterer
from backend.analysis.llm_client import get_llm_client
from typing import List, Dict, Any

router = APIRouter()

def run_analysis_task(run_id: int, db: Session):
    # Set analysis status to 'analyzing'
    run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
    if run:
        run.analysis_status = "analyzing"
        db.commit()

    try:
        # 1. Fetch all failures for the run
        failures = db.query(models.TestCase).filter(
            models.TestCase.test_run_id == run_id,
            models.TestCase.status == "fail"
        ).all()
        
        if not failures:
            # No failures, mark completed
            if run:
                run.analysis_status = "completed"
                db.commit()
            return

        # 2. Prepare failure data for improved clustering
        # The new clusterer uses enriched features including module/class/method
        failure_dicts = [
            {
                'module_name': f.module_name or '',
                'class_name': f.class_name or '',
                'method_name': f.method_name or '',
                'stack_trace': f.stack_trace or '',
                'error_message': f.error_message or ''
            }
            for f in failures
        ]
        
        # Filter out failures with no useful text
        valid_indices = [
            i for i, fd in enumerate(failure_dicts) 
            if fd['stack_trace'].strip() or fd['error_message'].strip()
        ]
        valid_failure_dicts = [failure_dicts[i] for i in valid_indices]
        
        if not valid_failure_dicts:
            if run:
                run.analysis_status = "completed"
                db.commit()
            return

        # 3. Cluster using improved algorithm with HDBSCAN
        clusterer = ImprovedFailureClusterer(min_cluster_size=2)
        labels, metrics = clusterer.cluster_failures(valid_failure_dicts)
        
        # Handle outliers by grouping them by module
        labels = clusterer.handle_outliers(valid_failure_dicts, labels)
        
        # Log clustering metrics
        print(f"[Run {run_id}] Clustering completed: {metrics}")
        
        # Get cluster summary for debugging
        cluster_summary = clusterer.get_cluster_summary(valid_failure_dicts, labels)
        for cluster_id, info in cluster_summary.items():
            print(f"  Cluster {cluster_id}: {info['count']} failures, "
                  f"modules={info['modules']}, purity={info['purity']:.2f}")
        
        # 4. Group by cluster and analyze representative
        clusters: Dict[int, List] = {}
        for idx, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(failures[valid_indices[idx]])
            
        llm_client = get_llm_client()
        
        # Prepare for parallel execution
        analysis_tasks = []
        cluster_map = {} # Map cluster_id to cluster object for easy update
        
        # 3.1 Pre-create clusters and prepare tasks (Main Thread)
        for label, cluster_failures in clusters.items():
            # Create a Cluster record
            rep = cluster_failures[0]
            signature = (rep.stack_trace if rep.stack_trace and rep.stack_trace.strip() else rep.error_message)[:500]
            
            db_cluster = db.query(models.FailureCluster).filter(models.FailureCluster.signature == signature).first()
            
            if not db_cluster:
                db_cluster = models.FailureCluster(
                    signature=signature,
                    description=f"Cluster {label} with {len(cluster_failures)} failures"
                )
                db.add(db_cluster)
                db.commit()
                db.refresh(db_cluster)
            
            cluster_map[db_cluster.id] = db_cluster
            
            # Build comprehensive failure context
            representative_failure = cluster_failures[0]
            failure_context = f"""
Test Failure Details:
- Module: {representative_failure.module_name or 'Unknown'}
- Test Class: {representative_failure.class_name or 'Unknown'}
- Test Method: {representative_failure.method_name or 'Unknown'}
- Error Message: {representative_failure.error_message or 'No error message'}
- Stack Trace: {representative_failure.stack_trace or 'No stack trace available'}
- Number of similar failures in cluster: {len(cluster_failures)}
"""
            analysis_tasks.append({
                "cluster_id": db_cluster.id,
                "context": failure_context,
                "failures": cluster_failures # Keep reference to failures for linking later
            })

        # 3.2 Execute Analysis in Parallel (Worker Threads)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def analyze_single_cluster(task):
            try:
                # Re-instantiate client or use thread-safe client if needed. 
                # OpenAI client is generally thread-safe for sync calls.
                result = llm_client.analyze_failure(task["context"])
                return {"cluster_id": task["cluster_id"], "result": result, "failures": task["failures"]}
            except Exception as e:
                print(f"Analysis failed for cluster {task['cluster_id']}: {e}")
                return {"cluster_id": task["cluster_id"], "error": str(e), "failures": task["failures"]}

        # Use 5 workers to balance speed and rate limits
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_cluster = {executor.submit(analyze_single_cluster, task): task for task in analysis_tasks}
            for future in as_completed(future_to_cluster):
                results.append(future.result())

        # 3.3 Save Results (Main Thread)
        for res in results:
            cluster_id = res["cluster_id"]
            db_cluster = cluster_map.get(cluster_id)
            
            if "error" in res:
                # Handle error case
                db_cluster.ai_summary = f"Analysis Failed: {res['error']}"
                db_cluster.severity = "Low"
                db.commit()
                continue

            analysis_result = res["result"]
            
            # Handle both dict (new) and str (legacy/fallback)
            if isinstance(analysis_result, dict):
                root_cause = analysis_result.get("root_cause", "Unknown")
                if isinstance(root_cause, list):
                    root_cause = "\n".join(str(item) for item in root_cause)
                    
                solution = analysis_result.get("solution", "No solution provided")
                if isinstance(solution, list):
                    solution = "\n".join(str(item) for item in solution)
                    
                ai_summary = analysis_result.get("ai_summary", "Analysis pending...")
                severity = analysis_result.get("severity", "Medium")
                category = analysis_result.get("category", "Uncategorized")
                confidence_score = analysis_result.get("confidence_score", 0)
                suggested_assignment = analysis_result.get("suggested_assignment", "Unknown")
            else:
                # Fallback for string response
                root_cause = "See summary"
                solution = "See summary"
                ai_summary = str(analysis_result)
                severity = "Medium"
                category = "Uncategorized"
                confidence_score = 0
                suggested_assignment = "Unknown"
            
            # Update cluster with analysis
            db_cluster.common_root_cause = root_cause
            db_cluster.common_solution = solution
            db_cluster.ai_summary = ai_summary
            db_cluster.severity = severity
            db_cluster.category = category
            db_cluster.confidence_score = confidence_score
            db_cluster.suggested_assignment = suggested_assignment
            db.commit()
            
            # Link all failures in this cluster to the analysis
            for failure in res["failures"]:
                # Check if analysis already exists
                existing_analysis = db.query(models.FailureAnalysis).filter(models.FailureAnalysis.test_case_id == failure.id).first()
                
                if existing_analysis:
                    existing_analysis.cluster_id = db_cluster.id
                    existing_analysis.root_cause = root_cause
                    existing_analysis.suggested_solution = solution
                else:
                    analysis_record = models.FailureAnalysis(
                        test_case_id=failure.id,
                        cluster_id=db_cluster.id,
                        root_cause=root_cause,
                        suggested_solution=solution
                    )
                    db.add(analysis_record)
                db.commit()
        
        # Mark analysis as completed
        if run:
            run.analysis_status = "completed"
            db.commit()
            
    except Exception as e:
        print(f"Analysis failed: {e}")
        if run:
            run.analysis_status = "failed"
            db.commit()

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
    background_tasks.add_task(run_analysis_task, run_id, db)
    
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
                if issue and 'status' in issue:
                    cluster_dict["redmine_status"] = issue['status'].get('name', 'Unknown')
                    cluster_dict["redmine_status_id"] = issue['status'].get('id', 0)
                else:
                    cluster_dict["redmine_status"] = None
                    cluster_dict["redmine_status_id"] = None
            except:
                cluster_dict["redmine_status"] = None
                cluster_dict["redmine_status_id"] = None
        else:
            cluster_dict["redmine_status"] = None
            cluster_dict["redmine_status_id"] = None
        
        enhanced_clusters.append(cluster_dict)
        
    return enhanced_clusters

@router.get("/cluster/{cluster_id}/failures")
def get_cluster_failures(cluster_id: int, db: Session = Depends(get_db)):
    # Get all failures associated with this cluster
    failures = db.query(models.TestCase).join(models.FailureAnalysis).filter(
        models.FailureAnalysis.cluster_id == cluster_id
    ).limit(50).all() # Limit to 50 for now
    return failures
