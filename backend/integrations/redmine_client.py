import requests
from typing import Optional, Dict, List, Any

class RedmineClient:
    def __init__(self, url: str, api_key: str):
        # Smart URL handling: 
        # If running in Docker (implied by this code running on backend) and URL provides localhost, 
        # swap to host.docker.internal to allow connection to host machine.
        processed_url = url.replace('localhost', 'host.docker.internal').replace('127.0.0.1', 'host.docker.internal')
        
        self.url = processed_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'X-Redmine-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> bool:
        """Test if the credentials are valid by fetching current user."""
        try:
            response = requests.get(f"{self.url}/users/current.json", headers=self.headers, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Redmine connection test failed: {e}")
            return False

    def get_projects(self) -> List[Dict[str, Any]]:
        """Fetch list of projects."""
        try:
            response = requests.get(f"{self.url}/projects.json", headers=self.headers, params={'limit': 100})
            if response.status_code == 200:
                return response.json().get('projects', [])
            return []
        except Exception as e:
            print(f"Failed to fetch projects: {e}")
            return []

    def search_issues(self, query: str) -> List[Dict[str, Any]]:
        """Search for issues matching the query."""
        try:
            # Redmine search API is a bit limited, often better to filter issues
            # For simplicity, we'll search open issues with the subject containing the query
            params = {
                'subject': f"~{query}",
                'status_id': 'open',
                'limit': 20
            }
            response = requests.get(f"{self.url}/issues.json", headers=self.headers, params=params)
            if response.status_code == 200:
                return response.json().get('issues', [])
            return []
        except Exception as e:
            print(f"Failed to search issues: {e}")
            return []

    def get_users(self, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch list of users. If project_id is provided, fetches members of that project."""
        try:
            if project_id:
                # Fetch memberships for the project to get users
                url = f"{self.url}/projects/{project_id}/memberships.json"
                print(f"Fetching users from: {url}")
                response = requests.get(url, headers=self.headers, params={'limit': 100})
                print(f"Redmine response: {response.status_code}")
                if response.status_code != 200:
                    print(f"Error response: {response.text}")
                
                if response.status_code == 200:
                    memberships = response.json().get('memberships', [])
                    # Extract user info from memberships
                    users = []
                    for m in memberships:
                        if 'user' in m:
                            users.append(m['user'])
                    return users
            else:
                # Fetch all users (requires admin or specific permissions usually)
                url = f"{self.url}/users.json"
                print(f"Fetching users from: {url}")
                response = requests.get(url, headers=self.headers, params={'limit': 100})
                print(f"Redmine response: {response.status_code}")
                
                if response.status_code == 200:
                    return response.json().get('users', [])
            return []
        except Exception as e:
            print(f"Failed to fetch users: {e}")
            return []

    def create_issue(self, project_id: int, subject: str, description: str, priority_id: int = 4, parent_issue_id: Optional[int] = None, assigned_to_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Create a new issue."""
        try:
            payload = {
                'issue': {
                    'project_id': project_id,
                    'subject': subject,
                    'description': description,
                    'priority_id': priority_id
                }
            }
            if parent_issue_id:
                payload['issue']['parent_issue_id'] = parent_issue_id
            if assigned_to_id:
                payload['issue']['assigned_to_id'] = assigned_to_id
                
            response = requests.post(f"{self.url}/issues.json", headers=self.headers, json=payload)
            if response.status_code == 201:
                return response.json().get('issue')
            else:
                error_msg = f"Redmine Error ({response.status_code}): {response.text}"
                print(f"Failed to create issue: {error_msg}")
                raise Exception(error_msg)
        except Exception as e:
            print(f"Error creating issue: {e}")
            raise e

    def get_issue(self, issue_id: int) -> Optional[Dict[str, Any]]:
        """Get details of a specific issue."""
        try:
            response = requests.get(f"{self.url}/issues/{issue_id}.json", headers=self.headers)
            if response.status_code == 200:
                return response.json().get('issue')
            return None
        except Exception as e:
            print(f"Error fetching issue {issue_id}: {e}")
            return None

    def add_note_to_issue(self, issue_id: int, note: str) -> bool:
        """
        Add a note/comment to an existing issue.
        
        Args:
            issue_id: Redmine issue ID
            note: The note content to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            payload = {
                'issue': {
                    'notes': note
                }
            }
            response = requests.put(
                f"{self.url}/issues/{issue_id}.json",
                headers=self.headers,
                json=payload
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error adding note to issue {issue_id}: {e}")
            return False

    def reopen_issue(self, issue_id: int, note: str = "Regression detected") -> bool:
        """
        Reopen a closed issue (for regression detection).
        
        Args:
            issue_id: Redmine issue ID
            note: Note to add explaining the reopen
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Status ID 1 is typically "New" in Redmine, adjust based on your config
            payload = {
                'issue': {
                    'status_id': 1,
                    'notes': note
                }
            }
            response = requests.put(
                f"{self.url}/issues/{issue_id}.json",
                headers=self.headers,
                json=payload
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error reopening issue {issue_id}: {e}")
            return False

    def search_issues_by_subject(self, subject_query: str, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for issues by subject (for deduplication).
        
        Args:
            subject_query: Text to search in issue subjects
            project_id: Optional project ID to narrow search
            
        Returns:
            List of matching issues
        """
        try:
            params = {
                'subject': f"~{subject_query}",
                'limit': 20
            }
            if project_id:
                params['project_id'] = project_id
            
            response = requests.get(f"{self.url}/issues.json", headers=self.headers, params=params)
            if response.status_code == 200:
                return response.json().get('issues', [])
            return []
        except Exception as e:
            print(f"Error searching issues: {e}")
            return []


def generate_issue_content(
    cluster_data: Dict[str, Any],
    run_data: Dict[str, Any],
    module_name: str,
    failures: List[Dict[str, Any]],
    app_url: str = "http://localhost:8000"
) -> Dict[str, str]:
    """
    Generate standardized Redmine issue subject and description.
    
    Args:
        cluster_data: Cluster information (ai_summary, root_cause, severity, etc.)
        run_data: Test run metadata (build_id, fingerprint, etc.)
        module_name: The module this ticket is for
        failures: List of failures in this cluster for this module
        app_url: The application base URL for deep links
        
    Returns:
        Dict with 'subject' and 'description' keys
    """
    # Extract AI summary (first line if multi-line)
    ai_summary = cluster_data.get('ai_summary', 'Unknown Issue')
    title = ai_summary.split('\n')[0][:80] if ai_summary else 'Unknown Issue'
    
    android_version = run_data.get('android_version', 'Unknown')
    
    # Generate subject
    subject = f"[GMS][{android_version}][{module_name}] {title}"
    
    # Generate description
    root_cause = cluster_data.get('common_root_cause', 'N/A')
    solution = cluster_data.get('common_solution', 'N/A')
    severity = cluster_data.get('severity', 'Medium')
    
    # helper to quote logical blocks
    def to_blockquote(text):
        if not text: return "> N/A"
        return '\n'.join([f"> {line}" for line in text.split('\n')])

    quoted_root_cause = to_blockquote(root_cause)
    quoted_solution = to_blockquote(solution)
    
    # Get representative failure
    rep_failure = failures[0] if failures else {}
    stack_trace = rep_failure.get('stack_trace', 'No stack trace available')
    # Limit stack trace to ~50 lines
    stack_lines = stack_trace.split('\n')[:50]
    truncated_stack = '\n'.join(stack_lines)
    if len(stack_lines) == 50:
        truncated_stack += '\n... (truncated)'
    
    # Build affected tests list (All)
    affected_tests = []
    # Base URL for deep links
    base_url = app_url.rstrip('/')
    
    for i, f in enumerate(failures):
        test_name = f"{f.get('class_name', 'Unknown')}.{f.get('method_name', 'unknown')}"
        # Determine TC ID to build link (assuming 'id' is available in failure dict)
        tc_id = f.get('id')
        if tc_id:
            link = f"{base_url}/?page=test-case&id={tc_id}"
            affected_tests.append(f"{i+1}. [{test_name}]({link})")
        else:
            affected_tests.append(f"{i+1}. {test_name}")
    
    description = f"""### AI Analysis

**Root Cause**
{quoted_root_cause}

**Suggestion**
{quoted_solution}

**Impact Analysis**
* **Severity**: {severity}
* **Impact**: {len(failures)} test(s) failed (Cluster ID: #{cluster_data.get('id', 'N/A')})

---

### Environment

* **Product**: {run_data.get('build_product', 'N/A')}
* **Build ID**: {run_data.get('build_id', 'N/A')}
* **Fingerprint**: {run_data.get('device_fingerprint', 'N/A')}
* **Suite Version**: {run_data.get('suite_version', 'N/A')}

---

### Technical Details

**Stack Trace Signature**
```text
{cluster_data.get('signature', 'N/A')}
```

**Representative Stack Trace**
```java
{truncated_stack}
```

### Affected Tests (Top 50)
{chr(10).join(affected_tests[:50])}
{f"{chr(10)}... and {len(affected_tests) - 50} more" if len(affected_tests) > 50 else ""}
"""
    
    return {
        'subject': subject,
        'description': description
    }

