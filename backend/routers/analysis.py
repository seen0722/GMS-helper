from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from backend.database.database import get_db, SessionLocal
from backend.database import models
from backend.analysis.clustering import ImprovedFailureClusterer
from backend.analysis.llm_client import get_llm_client
from typing import List, Dict, Any, Optional
import traceback

router = APIRouter()

def run_analysis_task(run_id: int):
    print(f"--- Starting Analysis Task for Run {run_id} ---")
    db = SessionLocal()
    try:
        # Set analysis status to 'analyzing'
        run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
        if run:
            run.analysis_status = "analyzing"
            db.commit()
            print(f"Run {run_id} status set to analyzing")

        # 1. Fetch all failures for the run
        failures = db.query(models.TestCase).filter(
            models.TestCase.test_run_id == run_id,
            models.TestCase.status == "fail"
        ).all()
        
        print(f"Fetched {len(failures)} failures")
        
        if not failures:
            # No failures, mark completed
            if run:
                run.analysis_status = "completed"
                db.commit()
            return

        # --- OPTIMIZATION: Skip Recovered Failures ---
        # If this is an older run and the failures were fixed in a newer run, skip analyzing them.
        failures_to_analyze = []
        recovered_failures = []
        
        # 1. Get subsequent runs for this submission & suite
        submission_id = run.submission_id
        if submission_id:
            # Get current suite type/name identity
            current_suite = run.test_suite_name
            # Find newer runs for the SAME suite in SAME submission
            candidate_runs = db.query(models.TestRun).filter(
                models.TestRun.submission_id == submission_id,
                models.TestRun.test_suite_name == current_suite,
                models.TestRun.start_time > run.start_time
            ).order_by(models.TestRun.start_time.desc()).all()

            # Strict GSI Separation
            # GSI runs have 'gsi' in product or model. Standard runs do not (or match target fingerprint).
            def is_gsi(r):
                plan = (r.suite_plan or "").lower()
                prod = (r.build_product or "").lower()
                mod = (r.build_model or "").lower()
                return "cts-on-gsi" in plan or "gsi" in prod or "gsi" in mod

            current_is_gsi = is_gsi(run)
            newer_runs = [r for r in candidate_runs if is_gsi(r) == current_is_gsi]
            
            if newer_runs:
                print(f"Found {len(newer_runs)} newer matching runs (GSI={current_is_gsi}). Checking for recovery...")
                # Get all failures in newer runs to check persistence
                # We collect a set of (module, class, method) that FAILED in ANY newer run.
                # If a test case is NOT in this set, it implies it PASSED (Recovered) in the latest relevant run 
                # (assuming comprehensive retry or at least retry of failures).
                
                # To be precise: If it failed in Run A, and we have Run B (newer).
                # If it's NOT in Run B's failures, it recovered.
                # If we have Run B and Run C. 
                # If it failed in A, passed in B, failed in C -> It is currently FAILING (Regression/Persistent).
                # So we should look at the LATEST run.
                
                latest_run = newer_runs[0] # Ordered by desc
                latest_failures = db.query(models.TestCase).filter(
                    models.TestCase.test_run_id == latest_run.id,
                    models.TestCase.status == "fail"
                ).all()
                
                latest_fail_keys = set(
                    (f.module_name, f.class_name, f.method_name, f.module_abi or '') 
                    for f in latest_failures
                )
                
                for f in failures:
                    key = (f.module_name, f.class_name, f.method_name, f.module_abi or '')
                    if key in latest_fail_keys:
                        # Still failing in latest run
                        failures_to_analyze.append(f)
                    else:
                        # Recovered!
                        recovered_failures.append(f)
                        
                print(f"Optimization: {len(recovered_failures)} failures recovered, {len(failures_to_analyze)} persistent.")
            else:
                failures_to_analyze = list(failures)
        else:
            failures_to_analyze = list(failures)
            
        # Handle Recovered Failures (Mark them so they don't look unanalyzed)
        if recovered_failures:
            # Create/Find a specialized cluster for "Recovered"
            # We use a special signature
            rec_sig = "RECOVERED_IN_LATER_RUNS"
            rec_cluster = db.query(models.FailureCluster).filter(models.FailureCluster.signature == rec_sig).first()
            if not rec_cluster:
                rec_cluster = models.FailureCluster(
                    signature=rec_sig,
                    description="Failures that passed in subsequent retries",
                    common_root_cause="Transient issue or Fixed in retry",
                    common_solution="No action needed - Verified manually or by retry",
                    severity="Low",
                    category="Recovered",
                    ai_summary="These test cases failed intially but passed in a subsequent test run within the same submission. They are considered recovered.",
                    confidence_score=100
                )
                db.add(rec_cluster)
                db.commit()
                db.refresh(rec_cluster)
            
            # Link failures
            for f in recovered_failures:
                # Check if analysis exists
                exists = db.query(models.FailureAnalysis).filter(models.FailureAnalysis.test_case_id == f.id).first()
                if not exists:
                    analysis = models.FailureAnalysis(
                        test_case_id=f.id,
                        cluster_id=rec_cluster.id,
                        root_cause="Recovered",
                        suggested_solution="Fixed in retry"
                    )
                    db.add(analysis)
            db.commit()
            
        # Continue with only persistent failures
        failures = failures_to_analyze
        if not failures:
            print("All failures recovered! Marking analysis complete.")
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
        
        print(f"Valid failures for clustering: {len(valid_failure_dicts)}")
        
        if not valid_failure_dicts:
            if run:
                run.analysis_status = "completed"
                db.commit()
            return

        # 3. Cluster using improved algorithm with HDBSCAN
        # PRD Phase 1.2: min_cluster_size=3 to reduce fragmentation while maintaining granularity
        clusterer = ImprovedFailureClusterer(min_cluster_size=3)
        labels, metrics = clusterer.cluster_failures(valid_failure_dicts)
        
        # Handle outliers by grouping them by module
        labels = clusterer.handle_outliers(valid_failure_dicts, labels)
        
        # P1: Merge small clusters with same module+class to reduce fragmentation
        labels = clusterer.merge_small_clusters(valid_failure_dicts, labels, max_merge_size=2)
        
        # Log clustering metrics
        n_clusters_after_merge = len(set(labels))
        print(f"[Run {run_id}] Clustering completed: {metrics}")
        print(f"[Run {run_id}] After merge: {n_clusters_after_merge} clusters (from {metrics.get('n_clusters', 0)})")
        
        # Get cluster summary for debugging
        cluster_summary = clusterer.get_cluster_summary(valid_failure_dicts, labels)
        for cluster_id, info in cluster_summary.items():
            print(f"  Cluster {cluster_id}: {info['count']} failures, "
                  f"modules={info['modules']}, purity={info['purity']:.2f}, exceptions={info['exceptions']}")
        
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

        print(f"Prepared {len(analysis_tasks)} analysis tasks")

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
                traceback.print_exc()
                return {"cluster_id": task["cluster_id"], "error": str(e), "failures": task["failures"]}

        # Use 5 workers to balance speed and rate limits
        results = []
        if analysis_tasks:
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_cluster = {executor.submit(analyze_single_cluster, task): task for task in analysis_tasks}
                for future in as_completed(future_to_cluster):
                    results.append(future.result())
        
        print(f"Analysis complete. Processing {len(results)} results")

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
            print(f"Run {run_id} analysis marked as completed")
            
    except Exception as e:
        print(f"Analysis task failed: {e}")
        traceback.print_exc()
        try:
            # Re-query session just in case
            run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
            if run:
                run.analysis_status = "failed"
                db.commit()
        except:
            pass
    finally:
        db.close()
        print(f"--- Analysis Task for Run {run_id} Finished (Session Closed) ---")

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
