from fastapi.testclient import TestClient
from backend.main import app
from backend.database.database import get_db

client = TestClient(app)

print("Testing routes:")
print("/api/reports/runs - ", "OK" if client.get("/api/reports/runs").status_code == 200 else "FAIL")
print("/api/reports/runs/14 - ", "OK" if client.get("/api/reports/runs/14").status_code == 200 else "FAIL")
print("/api/reports/runs/14/stats - ", "OK" if client.get("/api/reports/runs/14/stats").status_code == 200 else "FAIL")

# Show actual response for stats
response = client.get("/api/reports/runs/14/stats")
print(f"\nStats endpoint response:")
print(f"Status: {response.status_code}")
print(f"Body: {response.text}")
