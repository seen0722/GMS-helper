"""
Deduplication Service for Redmine Issues

This module implements smart deduplication logic:
1. Search for existing issues by cluster signature or module+error pattern
2. Decide whether to Create, Update (add note), or Reopen (regression)

Author: Chen Zeming
Date: 2026-01-17
"""

from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
import hashlib


class DuplicateAction(Enum):
    """Actions to take when checking for duplicates."""
    CREATE_NEW = "create_new"       # No duplicate found, create new issue
    ADD_NOTE = "add_note"           # Found open duplicate, add reproduction note
    REOPEN = "reopen"               # Found closed duplicate (regression)
    SKIP = "skip"                   # Already linked to this cluster


class DeduplicationService:
    """
    Service to check for and handle duplicate Redmine issues.
    """
    
    def __init__(self, redmine_client):
        """
        Initialize with a RedmineClient instance.
        
        Args:
            redmine_client: Configured RedmineClient
        """
        self.client = redmine_client
    
    def generate_signature_hash(self, cluster_signature: str) -> str:
        """
        Generate a short hash from cluster signature for searching.
        
        Args:
            cluster_signature: The cluster's stack trace signature
            
        Returns:
            8-character hash string
        """
        if not cluster_signature:
            return ""
        return hashlib.md5(cluster_signature.encode()).hexdigest()[:8]
    
    def extract_search_key(self, module_name: str, ai_summary: str) -> str:
        """
        Extract a search key from module and AI summary.
        
        Args:
            module_name: CTS module name
            ai_summary: AI-generated summary
            
        Returns:
            Search key string
        """
        # Use first line of summary (the title)
        title = ai_summary.split('\n')[0] if ai_summary else ""
        # Remove special characters that might break search
        title = title.replace('[', '').replace(']', '').replace('"', '')
        return f"{module_name} {title[:50]}"
    
    def check_for_duplicate(
        self,
        module_name: str,
        ai_summary: str,
        cluster_signature: Optional[str] = None,
        project_id: Optional[int] = None,
        existing_issue_id: Optional[int] = None
    ) -> Tuple[DuplicateAction, Optional[Dict[str, Any]]]:
        """
        Check if a similar issue already exists in Redmine.
        
        Args:
            module_name: CTS module name
            ai_summary: AI-generated summary
            cluster_signature: Optional cluster signature for hash matching
            project_id: Optional project ID to narrow search
            existing_issue_id: If cluster is already linked to an issue
            
        Returns:
            Tuple of (action_to_take, existing_issue_or_none)
        """
        # Case 1: Already linked to an issue
        if existing_issue_id:
            issue = self.client.get_issue(existing_issue_id)
            if issue:
                status_name = issue.get('status', {}).get('name', '').lower()
                # Check if it's closed/resolved
                if status_name in ['closed', 'resolved', 'rejected', 'done']:
                    return (DuplicateAction.REOPEN, issue)
                else:
                    return (DuplicateAction.SKIP, issue)
            # Issue doesn't exist anymore, create new
            return (DuplicateAction.CREATE_NEW, None)
        
        # Case 2: Search by subject pattern
        search_key = self.extract_search_key(module_name, ai_summary)
        if not search_key.strip():
            return (DuplicateAction.CREATE_NEW, None)
        
        matching_issues = self.client.search_issues_by_subject(search_key, project_id)
        
        if not matching_issues:
            return (DuplicateAction.CREATE_NEW, None)
        
        # Analyze the first match (most relevant)
        best_match = matching_issues[0]
        status_name = best_match.get('status', {}).get('name', '').lower()
        
        # Check status
        if status_name in ['closed', 'resolved', 'rejected', 'done']:
            return (DuplicateAction.REOPEN, best_match)
        elif status_name in ['new', 'open', 'in progress', 'feedback', 'assigned']:
            return (DuplicateAction.ADD_NOTE, best_match)
        
        # Default: create new if status is unclear
        return (DuplicateAction.CREATE_NEW, None)
    
    def generate_reproduction_note(
        self,
        build_id: str,
        fingerprint: str,
        failure_count: int,
        run_id: int
    ) -> str:
        """
        Generate a note for adding to existing issues.
        
        Args:
            build_id: Current build ID
            fingerprint: Device fingerprint
            failure_count: Number of failures in this run
            run_id: Test run ID for reference
            
        Returns:
            Formatted note string
        """
        return f"""h3. Issue Reproduced

This issue was reproduced in a new test run.

|_. Property|_. Value|
|Build ID|@{build_id}@|
|Fingerprint|@{fingerprint}@|
|Failure Count|{failure_count}|
|GMS Helper Run|#Run {run_id}|

_Auto-generated by GMS Helper_
"""
    
    def generate_regression_note(
        self,
        build_id: str,
        fingerprint: str,
        failure_count: int,
        run_id: int
    ) -> str:
        """
        Generate a note for reopening closed issues (regression).
        
        Args:
            build_id: Current build ID
            fingerprint: Device fingerprint
            failure_count: Number of failures
            run_id: Test run ID
            
        Returns:
            Formatted regression note
        """
        return f"""h3. ⚠️ REGRESSION DETECTED

This issue has reappeared after being marked as resolved.

|_. Property|_. Value|
|Build ID|@{build_id}@|
|Fingerprint|@{fingerprint}@|
|Failure Count|{failure_count}|
|GMS Helper Run|#Run {run_id}|

*Action Required:* Please investigate why this issue has regressed.

_Auto-generated by GMS Helper_
"""
    
    def execute_action(
        self,
        action: DuplicateAction,
        issue: Optional[Dict[str, Any]],
        note: str
    ) -> Dict[str, Any]:
        """
        Execute the determined action.
        
        Args:
            action: The action to take
            issue: The existing issue (if any)
            note: The note to add
            
        Returns:
            Result dict with status and details
        """
        if action == DuplicateAction.CREATE_NEW:
            return {"action": "create_new", "message": "No duplicate found, proceed to create"}
        
        elif action == DuplicateAction.SKIP:
            return {
                "action": "skip",
                "message": "Cluster already linked to open issue",
                "issue_id": issue['id'] if issue else None
            }
        
        elif action == DuplicateAction.ADD_NOTE:
            if issue:
                success = self.client.add_note_to_issue(issue['id'], note)
                return {
                    "action": "add_note",
                    "success": success,
                    "issue_id": issue['id'],
                    "message": "Added reproduction note to existing issue"
                }
            return {"action": "error", "message": "No issue to add note to"}
        
        elif action == DuplicateAction.REOPEN:
            if issue:
                success = self.client.reopen_issue(issue['id'], note)
                return {
                    "action": "reopen",
                    "success": success,
                    "issue_id": issue['id'],
                    "message": "Reopened issue (regression detected)"
                }
            return {"action": "error", "message": "No issue to reopen"}
        
        return {"action": "unknown", "message": "Unknown action"}


def get_deduplication_service(redmine_client) -> DeduplicationService:
    """Factory function to get DeduplicationService instance."""
    return DeduplicationService(redmine_client)
