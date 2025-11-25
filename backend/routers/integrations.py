from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database import models
from backend.utils import encryption
from backend.integrations.redmine_client import RedmineClient
from pydantic import BaseModel
from typing import Optional, List

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
    return projects

@router.get("/redmine/users")
def get_redmine_users(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    client = get_redmine_client(db)
    users = client.get_users(project_id)
    return users

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
