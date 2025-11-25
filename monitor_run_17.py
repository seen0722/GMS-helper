import requests
import time

run_id = 17

print("Monitoring Run 17 processing...")
while True:
    response = requests.get(f"http://localhost:8000/api/reports/runs/{run_id}")
    run = response.json()
    status = run.get("status")
    
    print(f"Status: {status}")
    
    if status == "completed":
        print("\nProcessing complete! Testing /stats endpoint...")
        stats_response = requests.get(f"http://localhost:8000/api/reports/runs/{run_id}/stats")
        print(f"Stats status code: {stats_response.status_code}")
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print("\nStatistics:")
            print(f"  Total Modules: {stats.get('total_modules')}")
            print(f"  Passed Modules: {stats.get('passed_modules')}")
            print(f"  Failed Modules: {stats.get('failed_modules')}")
            print(f"  Total Tests: {stats.get('total_tests')}")
            print(f"  Passed Tests: {stats.get('passed_tests')}")
            print(f"  Failed Tests: {stats.get('failed_tests')}")
            print(f"  Ignored Tests: {stats.get('ignored_tests')}")
        else:
            print(f"Error: {stats_response.text}")
        break
    elif status == "failed":
        print("Processing failed!")
        break
    
    time.sleep(30)  # Wait 30 seconds before checking again
