from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database import models
from backend.utils import encryption
from backend.integrations.redmine_client import RedmineClient, generate_issue_content
from backend.integrations.assignment_resolver import get_assignment_resolver
from backend.integrations.deduplication_service import DeduplicationService, DuplicateAction, get_deduplication_service
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter()

class CreateIssueRequest(BaseModel):
    project_id: int
    subject: str
    description: str
    cluster_id: int
    create_children: bool = False
    assigned_to_id: Optional[int] = None

class LinkIssueRequest(BaseModel):
    issue_id: int
    cluster_id: int

def get_redmine_client(db: Session) -> RedmineClient:
    settings = db.query(models.Settings).first()
    if not settings or not settings.redmine_url or not settings.redmine_api_key:
        raise HTTPException(status_code=400, detail="Redmine settings not configured")
    
    try:
        api_key = encryption.decrypt(settings.redmine_api_key)
        return RedmineClient(settings.redmine_url, api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to decrypt Redmine API key")

@router.post("/redmine/test")
def test_redmine_connection(db: Session = Depends(get_db)):
    client = get_redmine_client(db)
    success = client.test_connection()
    return {"success": success}

@router.get("/redmine/projects")
def get_redmine_projects(db: Session = Depends(get_db)):
    client = get_redmine_client(db)
    projects = client.get_projects()
    return {"projects": projects}

@router.get("/redmine/users")
def get_redmine_users(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    client = get_redmine_client(db)
    users = client.get_users(project_id)
    return {"users": users}

@router.get("/redmine/search")
def search_redmine_issues(query: str, db: Session = Depends(get_db)):
    client = get_redmine_client(db)
    issues = client.search_issues(query)
    return issues

@router.post("/redmine/issue")
def create_redmine_issue(request: CreateIssueRequest, db: Session = Depends(get_db)):
    client = get_redmine_client(db)
    
    # 1. Create Issue in Redmine
    try:
        issue = client.create_issue(
            project_id=request.project_id, 
            subject=request.subject, 
            description=request.description,
            assigned_to_id=request.assigned_to_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create issue in Redmine: {str(e)}")
    
    # 2. Link Cluster to Issue
    cluster = db.query(models.FailureCluster).filter(models.FailureCluster.id == request.cluster_id).first()
    if cluster:
        cluster.redmine_issue_id = issue['id']
        db.commit()
        
        # 3. Create Child Issues (if requested)
        if request.create_children:
            # Fetch failures for this cluster
            failures = db.query(models.FailureAnalysis).filter(models.FailureAnalysis.cluster_id == cluster.id).all()
            
            # Create child issues for all failures
            for analysis in failures:
                    
                test_case = analysis.test_case
                child_subject = f"[Failure] {test_case.module_name} - {test_case.class_name}#{test_case.method_name}"
                child_desc = f"""*Module:* {test_case.module_name}
*Test Case:* {test_case.class_name}#{test_case.method_name}
*Error Message:*
<pre>
{test_case.error_message or 'N/A'}
</pre>

*Stack Trace:*
<pre>
{test_case.stack_trace or 'N/A'}
</pre>
"""
                client.create_issue(
                    project_id=request.project_id,
                    subject=child_subject,
                    description=child_desc,
                    parent_issue_id=issue['id'],
                    assigned_to_id=request.assigned_to_id
                )
    
    return issue

@router.post("/redmine/link")
def link_redmine_issue(request: LinkIssueRequest, db: Session = Depends(get_db)):
    client = get_redmine_client(db)
    
    # Verify issue exists
    issue = client.get_issue(request.issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Redmine issue not found")
        
    # Link Cluster
    cluster = db.query(models.FailureCluster).filter(models.FailureCluster.id == request.cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
        
    cluster.redmine_issue_id = request.issue_id
    db.commit()
    
    return {"message": "Cluster linked to issue successfully", "issue": issue}
class UnlinkIssueRequest(BaseModel):
    cluster_id: int

@router.post("/redmine/unlink")
def unlink_redmine_issue(request: UnlinkIssueRequest, db: Session = Depends(get_db)):
    # Find Cluster
    cluster = db.query(models.FailureCluster).filter(models.FailureCluster.id == request.cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
        
    cluster.redmine_issue_id = None
    db.commit()
    
    return {"message": "Cluster unlinked from issue successfully"}

class BulkCreateRequest(BaseModel):
    run_id: int
    project_id: int
    create_children: bool = False

@router.post("/redmine/bulk-create")
def bulk_create_redmine_issues(request: BulkCreateRequest, db: Session = Depends(get_db)):
    client = get_redmine_client(db)
    
    # Get all clusters for this run that don't have Redmine issues
    clusters = db.query(models.FailureCluster).join(models.FailureAnalysis).join(models.TestCase).filter(
        models.TestCase.test_run_id == request.run_id,
        models.FailureCluster.redmine_issue_id == None
    ).distinct().all()
    
    if not clusters:
        return {"message": "No clusters without Redmine issues", "created": 0}
    
    # Get test run details for system info
    run = db.query(models.TestRun).filter(models.TestRun.id == request.run_id).first()
    
    created_count = 0
    failed_count = 0
    results = []
    
    for cluster in clusters:
        try:
            # Get failures for this cluster
            failures = db.query(models.FailureAnalysis).filter(
                models.FailureAnalysis.cluster_id == cluster.id
            ).limit(5).all()
            
            # Determine suite tag
            suite_tag = "GMS"
            if run.test_suite_name:
                name_upper = run.test_suite_name.upper()
                if "CTS" in name_upper: suite_tag = "CTS"
                elif "GTS" in name_upper: suite_tag = "GTS"
                elif "VTS" in name_upper: suite_tag = "VTS"
                elif "STS" in name_upper: suite_tag = "STS"
                else: suite_tag = run.test_suite_name

            # Build issue subject - use first line of summary as title
            summary = cluster.ai_summary or cluster.description or "Unknown Issue"
            # Extract first line as title
            title = summary.split('\n')[0] if summary else "Unknown Issue"
            subject = f"[ {suite_tag} ] {title}"
            if len(subject) > 100:
                subject = subject[:97] + "..."
            
            # Format failures list
            failures_text = ""
            if failures:
                for idx, f in enumerate(failures):
                    stack_trace = f.test_case.stack_trace[:800] + ('\n...\n(truncated)' if len(f.test_case.stack_trace or '') > 800 else '') if f.test_case.stack_trace else 'N/A'
                    failures_text += f"""
h4. Failure {idx + 1}

* *Module:* @{f.test_case.module_name}@
* *Test Case:* @{f.test_case.class_name}#{f.test_case.method_name}@
* *Stack Trace:*

<pre><code class="java">
{stack_trace}
</code></pre>
"""
                if len(failures) == 5:
                     failures_text += f"\np(. _... and more failures not shown_\n"

            description = f"""h2. Failure Analysis Report

h3. Cluster Summary

|_. Property|_. Value|
|Cluster ID|#{ cluster.id}|
|Severity|{cluster.severity or 'Unknown'}|
|Category|{cluster.category or 'Uncategorized'}|
|Confidence|{cluster.confidence_score or 0}/5|
|Impact|{len(failures)} failures|

h3. System Information

|_. Property|_. Value|
|Fingerprint|@{run.device_fingerprint or 'N/A'}@|
|Build ID|@{run.build_id or 'N/A'}@|
|Product|{run.build_product or 'N/A'}|
|Model|{run.build_model or 'N/A'}|
|Android Version|{run.android_version or 'N/A'}|
|Security Patch|{run.security_patch or 'N/A'}|
|Test Suite|{run.test_suite_name or 'N/A'}|

h3. AI Analysis

*Summary:*
{cluster.ai_summary or 'N/A'}

*Root Cause:*
<pre>
{cluster.common_root_cause or 'N/A'}
</pre>

*Suggested Solution:*
{cluster.common_solution or 'N/A'}

h3. Technical Details

*Stack Trace Signature:*
<pre><code>
{cluster.signature or 'N/A'}
</code></pre>

h3. Affected Test Cases

{failures_text}
"""
            
            # Create parent issue
            issue = client.create_issue(request.project_id, subject, description)
            
            if issue:
                # Link cluster to issue
                cluster.redmine_issue_id = issue['id']
                db.commit()
                created_count += 1
                results.append({"cluster_id": cluster.id, "issue_id": issue['id'], "status": "created"})
                
                # Create child issues if requested
                if request.create_children:
                    all_failures = db.query(models.FailureAnalysis).filter(
                        models.FailureAnalysis.cluster_id == cluster.id
                    ).all()
                    
                    for analysis in all_failures:
                        test_case = analysis.test_case
                        child_subject = f"[Failure] {test_case.module_name} - {test_case.class_name}#{test_case.method_name}"
                        child_desc = f"""*Module:* {test_case.module_name}
*Test Case:* {test_case.class_name}#{test_case.method_name}
*Error Message:*
<pre>
{test_case.error_message or 'N/A'}
</pre>

*Stack Trace:*
<pre>
{test_case.stack_trace[:800] if test_case.stack_trace else 'N/A'}
</pre>"""
                        client.create_issue(
                            project_id=request.project_id,
                            subject=child_subject,
                            description=child_desc,
                            parent_issue_id=issue['id']
                        )
            else:
                failed_count += 1
                results.append({"cluster_id": cluster.id, "status": "failed"})
                
        except Exception as e:
            failed_count += 1
            results.append({"cluster_id": cluster.id, "status": "error", "error": str(e)})
    
    return {
        "message": f"Created {created_count} issues, {failed_count} failed",
        "created": created_count,
        "failed": failed_count,
        "results": results
    }


# ============================================================
# Phase 2: Smart Issue Creation Endpoints (PRD Redmine Automation)
# ============================================================

class SmartPreviewRequest(BaseModel):
    """Request model for previewing issue content before creation."""
    cluster_id: int
    run_id: int
    module_name: Optional[str] = None  # If None, uses first module in cluster


class SmartCreateRequest(BaseModel):
    """Request model for smart issue creation with auto-assignment."""
    cluster_id: int
    run_id: int
    project_id: int
    module_name: Optional[str] = None  # For module-centric splitting
    # Override fields (optional - uses auto-resolved values if not provided)
    subject_override: Optional[str] = None
    description_override: Optional[str] = None
    assigned_to_id_override: Optional[int] = None
    priority_id_override: Optional[int] = None


@router.post("/redmine/preview-issue")
def preview_issue_content(request: SmartPreviewRequest, db: Session = Depends(get_db)):
    """
    Generate and preview issue content without creating it.
    
    This allows the frontend to show a pre-filled modal that users can review/edit.
    """
    # Get cluster
    cluster = db.query(models.FailureCluster).filter(
        models.FailureCluster.id == request.cluster_id
    ).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    # Get test run
    run = db.query(models.TestRun).filter(models.TestRun.id == request.run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    # Get failures for this cluster (optionally filtered by module)
    query = db.query(models.TestCase).join(models.FailureAnalysis).filter(
        models.FailureAnalysis.cluster_id == request.cluster_id,
        models.TestCase.test_run_id == request.run_id
    )
    
    if request.module_name:
        query = query.filter(models.TestCase.module_name == request.module_name)
    
    failures = query.all()
    if not failures:
        raise HTTPException(status_code=404, detail="No failures found for this cluster/module")
    
    # Determine module name
    module_name = request.module_name or failures[0].module_name or "Unknown"
    
    # Convert to dict format for generate_issue_content
    failure_dicts = [
        {
            "class_name": f.class_name,
            "method_name": f.method_name,
            "error_message": f.error_message,
            "stack_trace": f.stack_trace
        }
        for f in failures
    ]
    
    run_data = {
        "android_version": run.android_version,
        "build_id": run.build_id,
        "build_product": run.build_product,
        "device_fingerprint": run.device_fingerprint,
        "suite_version": run.suite_version
    }
    
    cluster_data = {
        "id": cluster.id,
        "ai_summary": cluster.ai_summary,
        "common_root_cause": cluster.common_root_cause,
        "common_solution": cluster.common_solution,
        "severity": cluster.severity,
        "category": cluster.category
    }
    
    # Generate content
    content = generate_issue_content(cluster_data, run_data, module_name, failure_dicts)
    
    # Get assignment resolution
    resolver = get_assignment_resolver()
    assignment = resolver.resolve_assignment(
        module_name=module_name,
        severity=cluster.severity or "Medium"
    )
    
    return {
        "subject": content["subject"],
        "description": content["description"],
        "module_name": module_name,
        "failure_count": len(failures),
        "assignment": {
            "team_name": assignment["team_name"],
            "user_id": assignment["user_id"],
            "priority_id": assignment["priority_id"]
        }
    }


@router.post("/redmine/smart-create")
def smart_create_issue(request: SmartCreateRequest, db: Session = Depends(get_db)):
    """
    Create a Redmine issue with auto-generated content and assignment.
    
    Supports module-centric splitting: if module_name is provided, only failures
    from that module are included in the ticket.
    """
    client = get_redmine_client(db)
    
    # Get cluster
    cluster = db.query(models.FailureCluster).filter(
        models.FailureCluster.id == request.cluster_id
    ).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    # Get test run
    run = db.query(models.TestRun).filter(models.TestRun.id == request.run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    # Get failures
    query = db.query(models.TestCase).join(models.FailureAnalysis).filter(
        models.FailureAnalysis.cluster_id == request.cluster_id,
        models.TestCase.test_run_id == request.run_id
    )
    
    if request.module_name:
        query = query.filter(models.TestCase.module_name == request.module_name)
    
    failures = query.all()
    if not failures:
        raise HTTPException(status_code=404, detail="No failures found")
    
    module_name = request.module_name or failures[0].module_name or "Unknown"
    
    # Generate content if not overridden
    if request.subject_override and request.description_override:
        subject = request.subject_override
        description = request.description_override
    else:
        failure_dicts = [
            {"class_name": f.class_name, "method_name": f.method_name,
             "error_message": f.error_message, "stack_trace": f.stack_trace}
            for f in failures
        ]
        run_data = {
            "android_version": run.android_version, "build_id": run.build_id,
            "build_product": run.build_product, "device_fingerprint": run.device_fingerprint,
            "suite_version": run.suite_version
        }
        cluster_data = {
            "id": cluster.id, "ai_summary": cluster.ai_summary,
            "common_root_cause": cluster.common_root_cause,
            "common_solution": cluster.common_solution,
            "severity": cluster.severity, "category": cluster.category
        }
        content = generate_issue_content(cluster_data, run_data, module_name, failure_dicts)
        subject = request.subject_override or content["subject"]
        description = request.description_override or content["description"]
    
    # Resolve assignment
    resolver = get_assignment_resolver()
    assignment = resolver.resolve_assignment(
        module_name=module_name,
        severity=cluster.severity or "Medium"
    )
    
    assigned_to_id = request.assigned_to_id_override or assignment["user_id"]
    priority_id = request.priority_id_override or assignment["priority_id"]
    
    # Create issue
    try:
        issue = client.create_issue(
            project_id=request.project_id,
            subject=subject,
            description=description,
            priority_id=priority_id,
            assigned_to_id=assigned_to_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create issue: {str(e)}")
    
    # Link cluster to issue
    cluster.redmine_issue_id = issue['id']
    db.commit()
    
    return {
        "issue": issue,
        "module_name": module_name,
        "failure_count": len(failures),
        "assignment_resolved": {
            "team_name": assignment["team_name"],
            "priority": priority_id
        }
    }


class ModuleCentricBulkRequest(BaseModel):
    """Request for module-centric bulk issue creation."""
    run_id: int
    project_id: int
    module_name: Optional[str] = None  # If provided, only sync clusters from this module


@router.post("/redmine/smart-bulk-create")
def smart_bulk_create_by_module(request: ModuleCentricBulkRequest, db: Session = Depends(get_db)):
    """
    Create Redmine issues using module-centric splitting strategy.
    
    For each cluster that spans multiple modules, creates separate tickets per module.
    This aligns with PRD §2.1 "Strict Module Splitting".
    
    NOTE: Once ANY ticket is created for a cluster, the cluster is marked as synced
    to prevent duplicate issues on subsequent calls.
    """
    client = get_redmine_client(db)
    resolver = get_assignment_resolver()
    
    # Get test run
    run = db.query(models.TestRun).filter(models.TestRun.id == request.run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    # Get all clusters for this run that don't have Redmine issues
    query = db.query(models.FailureCluster).join(models.FailureAnalysis).join(models.TestCase).filter(
        models.TestCase.test_run_id == request.run_id,
        models.FailureCluster.redmine_issue_id == None
    )
    
    # If module_name is specified, only get clusters that have failures in that module
    if request.module_name:
        query = query.filter(models.TestCase.module_name == request.module_name)
    
    clusters = query.distinct().all()
    
    if not clusters:
        return {"message": "No clusters without Redmine issues", "created": 0, "results": [], "module_filter": request.module_name}
    
    run_data = {
        "android_version": run.android_version, "build_id": run.build_id,
        "build_product": run.build_product, "device_fingerprint": run.device_fingerprint,
        "suite_version": run.suite_version
    }
    
    results = []
    created_count = 0
    skipped_count = 0
    
    for cluster in clusters:
        # IMPORTANT: Re-check if cluster was synced during this loop (race condition prevention)
        db.refresh(cluster)
        if cluster.redmine_issue_id is not None:
            skipped_count += 1
            results.append({
                "cluster_id": cluster.id,
                "module": "N/A",
                "status": "skipped",
                "reason": "Already synced during this batch"
            })
            continue
        
        # Get all failures for this cluster, grouped by module
        failures = db.query(models.TestCase).join(models.FailureAnalysis).filter(
            models.FailureAnalysis.cluster_id == cluster.id,
            models.TestCase.test_run_id == request.run_id
        ).all()
        
        # Group by module
        modules: Dict[str, List] = {}
        for f in failures:
            mod = f.module_name or "Unknown"
            if mod not in modules:
                modules[mod] = []
            modules[mod].append(f)
        
        cluster_data = {
            "id": cluster.id, "ai_summary": cluster.ai_summary,
            "common_root_cause": cluster.common_root_cause,
            "common_solution": cluster.common_solution,
            "severity": cluster.severity, "category": cluster.category
        }
        
        first_issue_id = None
        
        # Create one ticket per module (Module-Centric Splitting)
        for module_name, module_failures in modules.items():
            try:
                failure_dicts = [
                    {"class_name": f.class_name, "method_name": f.method_name,
                     "error_message": f.error_message, "stack_trace": f.stack_trace}
                    for f in module_failures
                ]
                
                content = generate_issue_content(cluster_data, run_data, module_name, failure_dicts)
                
                assignment = resolver.resolve_assignment(
                    module_name=module_name,
                    severity=cluster.severity or "Medium"
                )
                
                issue = client.create_issue(
                    project_id=request.project_id,
                    subject=content["subject"],
                    description=content["description"],
                    priority_id=assignment["priority_id"],
                    assigned_to_id=assignment["user_id"]
                )
                
                # Mark cluster as synced with the FIRST issue created
                # This prevents duplicate issues if user clicks again
                if first_issue_id is None:
                    first_issue_id = issue['id']
                    cluster.redmine_issue_id = first_issue_id
                    db.commit()
                
                created_count += 1
                results.append({
                    "cluster_id": cluster.id,
                    "module": module_name,
                    "issue_id": issue['id'],
                    "status": "created",
                    "assigned_to_id": assignment["user_id"],
                    "resolved_from": assignment["resolved_from"]
                })
                
            except Exception as e:
                results.append({
                    "cluster_id": cluster.id,
                    "module": module_name,
                    "status": "error",
                    "error": str(e)
                })
    
    return {
        "message": f"Created {created_count} module-centric tickets, skipped {skipped_count}",
        "created": created_count,
        "skipped": skipped_count,
        "results": results
    }


@router.get("/redmine/cluster/{cluster_id}/modules")
def get_cluster_modules(cluster_id: int, run_id: int, db: Session = Depends(get_db)):
    """
    Get list of modules affected by a cluster in a specific run.
    
    Useful for UI to show module-centric breakdown before bulk creation.
    """
    modules = db.query(
        models.TestCase.module_name,
        db.func.count(models.TestCase.id).label('failure_count')
    ).join(models.FailureAnalysis).filter(
        models.FailureAnalysis.cluster_id == cluster_id,
        models.TestCase.test_run_id == run_id
    ).group_by(models.TestCase.module_name).all()
    
    resolver = get_assignment_resolver()
    
    result = []
    for module_name, count in modules:
        assignment = resolver.resolve_assignment(module_name or "Unknown")
        result.append({
            "module_name": module_name,
            "failure_count": count,
            "suggested_assignee": assignment["user_id"],
            "suggested_priority": assignment["priority_id"]
        })
    
    return {"modules": result}


# ============================================================
# Phase 3: Deduplication Endpoints (PRD Redmine Automation)
# ============================================================

class DeduplicationCheckRequest(BaseModel):
    """Request to check for duplicate issues."""
    cluster_id: int
    run_id: int
    module_name: Optional[str] = None
    project_id: Optional[int] = None


@router.post("/redmine/check-duplicate")
def check_duplicate_issue(request: DeduplicationCheckRequest, db: Session = Depends(get_db)):
    """
    Check if a similar issue already exists in Redmine.
    
    Returns the recommended action: create_new, add_note, reopen, or skip.
    """
    client = get_redmine_client(db)
    dedup_service = get_deduplication_service(client)
    
    # Get cluster
    cluster = db.query(models.FailureCluster).filter(
        models.FailureCluster.id == request.cluster_id
    ).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    # Get module name
    if request.module_name:
        module_name = request.module_name
    else:
        # Get first module from cluster
        failure = db.query(models.TestCase).join(models.FailureAnalysis).filter(
            models.FailureAnalysis.cluster_id == request.cluster_id,
            models.TestCase.test_run_id == request.run_id
        ).first()
        module_name = failure.module_name if failure else "Unknown"
    
    # Check for duplicates
    action, existing_issue = dedup_service.check_for_duplicate(
        module_name=module_name,
        ai_summary=cluster.ai_summary or "",
        cluster_signature=cluster.signature,
        project_id=request.project_id,
        existing_issue_id=cluster.redmine_issue_id
    )
    
    return {
        "action": action.value,
        "existing_issue": {
            "id": existing_issue.get('id'),
            "subject": existing_issue.get('subject'),
            "status": existing_issue.get('status', {}).get('name')
        } if existing_issue else None,
        "cluster_id": cluster.id,
        "module_name": module_name
    }


class SmartCreateWithDedupRequest(BaseModel):
    """Request for smart issue creation with deduplication."""
    cluster_id: int
    run_id: int
    project_id: int
    module_name: Optional[str] = None
    force_create: bool = False  # If True, skip deduplication check


@router.post("/redmine/smart-create-with-dedup")
def smart_create_with_deduplication(request: SmartCreateWithDedupRequest, db: Session = Depends(get_db)):
    """
    Create a Redmine issue with full deduplication workflow.
    
    1. Check for existing duplicates
    2. If duplicate found: add note or reopen
    3. If no duplicate: create new issue
    
    This is the recommended endpoint for production use.
    """
    client = get_redmine_client(db)
    dedup_service = get_deduplication_service(client)
    resolver = get_assignment_resolver()
    
    # Get cluster
    cluster = db.query(models.FailureCluster).filter(
        models.FailureCluster.id == request.cluster_id
    ).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    # Get test run
    run = db.query(models.TestRun).filter(models.TestRun.id == request.run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    # Get failures
    query = db.query(models.TestCase).join(models.FailureAnalysis).filter(
        models.FailureAnalysis.cluster_id == request.cluster_id,
        models.TestCase.test_run_id == request.run_id
    )
    if request.module_name:
        query = query.filter(models.TestCase.module_name == request.module_name)
    
    failures = query.all()
    if not failures:
        raise HTTPException(status_code=404, detail="No failures found")
    
    module_name = request.module_name or failures[0].module_name or "Unknown"
    
    # Step 1: Check for duplicates (unless force_create is True)
    if not request.force_create:
        action, existing_issue = dedup_service.check_for_duplicate(
            module_name=module_name,
            ai_summary=cluster.ai_summary or "",
            cluster_signature=cluster.signature,
            project_id=request.project_id,
            existing_issue_id=cluster.redmine_issue_id
        )
    else:
        action = DuplicateAction.CREATE_NEW
        existing_issue = None
    
    # Step 2: Execute action based on duplicate check
    if action == DuplicateAction.SKIP:
        return {
            "action": "skip",
            "message": "Cluster already linked to open issue",
            "issue_id": existing_issue['id'] if existing_issue else None
        }
    
    elif action == DuplicateAction.ADD_NOTE:
        note = dedup_service.generate_reproduction_note(
            build_id=run.build_id or "Unknown",
            fingerprint=run.device_fingerprint or "Unknown",
            failure_count=len(failures),
            run_id=request.run_id
        )
        result = dedup_service.execute_action(action, existing_issue, note)
        return result
    
    elif action == DuplicateAction.REOPEN:
        note = dedup_service.generate_regression_note(
            build_id=run.build_id or "Unknown",
            fingerprint=run.device_fingerprint or "Unknown",
            failure_count=len(failures),
            run_id=request.run_id
        )
        result = dedup_service.execute_action(action, existing_issue, note)
        
        # Link cluster to the reopened issue
        if result.get("success") and existing_issue:
            cluster.redmine_issue_id = existing_issue['id']
            db.commit()
        
        return result
    
    # Step 3: Create new issue
    failure_dicts = [
        {"class_name": f.class_name, "method_name": f.method_name,
         "error_message": f.error_message, "stack_trace": f.stack_trace}
        for f in failures
    ]
    run_data = {
        "android_version": run.android_version, "build_id": run.build_id,
        "build_product": run.build_product, "device_fingerprint": run.device_fingerprint,
        "suite_version": run.suite_version
    }
    cluster_data = {
        "id": cluster.id, "ai_summary": cluster.ai_summary,
        "common_root_cause": cluster.common_root_cause,
        "common_solution": cluster.common_solution,
        "severity": cluster.severity, "category": cluster.category
    }
    
    content = generate_issue_content(cluster_data, run_data, module_name, failure_dicts)
    
    assignment = resolver.resolve_assignment(
        module_name=module_name,
        severity=cluster.severity or "Medium"
    )
    
    try:
        issue = client.create_issue(
            project_id=request.project_id,
            subject=content["subject"],
            description=content["description"],
            priority_id=assignment["priority_id"],
            assigned_to_id=assignment["user_id"]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create issue: {str(e)}")
    
    # Link cluster to new issue
    cluster.redmine_issue_id = issue['id']
    db.commit()
    
    return {
        "action": "create_new",
        "issue": issue,
        "module_name": module_name,
        "failure_count": len(failures),
        "assignment": {
            "team_name": assignment["team_name"],
            "priority_id": assignment["priority_id"]
        }
    }
