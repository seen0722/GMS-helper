import requests
import os

url = "http://localhost:8000/api/upload/"
file_path = "sample_cts.xml"

if not os.path.exists(file_path):
    print(f"File {file_path} not found.")
    exit(1)

with open(file_path, "rb") as f:
    files = {"file": (file_path, f, "text/xml")}
    print(f"Uploading {file_path}...")
    try:
        response = requests.post(url, files=files)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Upload failed: {e}")
