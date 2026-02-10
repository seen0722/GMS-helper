
import sys
import os

# Add parent directory to path so we can import backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.integrations.redmine_client import RedmineClient

def test_client():
    url = "http://127.0.0.1:3000"
    api_key = "59255fb7a78dfbbc6c3dff60260f0fec044b8d9e"
    
    print(f"Original URL: {url}")
    client = RedmineClient(url, api_key)
    print(f"Processed URL in client: {client.url}")
    
    print("\nTesting connection...")
    success = client.test_connection()
    print(f"Success: {success}")

if __name__ == "__main__":
    test_client()
