import requests

url = "http://localhost:8000/api/reports/runs/14/stats"
response = requests.get(url)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

# Also test other endpoints to see if they work
url2 = "http://localhost:8000/api/reports/runs/14"
response2 = requests.get(url2)
print(f"\nRun details status: {response2.status_code}")
