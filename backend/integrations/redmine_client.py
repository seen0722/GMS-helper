import requests
from typing import Optional, Dict, List, Any

class RedmineClient:
    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
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
