from backend.database.database import SessionLocal
from backend.database import models
from backend.routers.upload import process_upload_background
from backend.routers.analysis import run_analysis_task
import time
import os
import sys

# Increase recursion limit just in case, though iterparse shouldn't need it
sys.setrecursionlimit(2000)

def run_stress_test():
    file_path = "test.xml"
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found in {os.getcwd()}")
        return

    print(f"Found {file_path}, size: {os.path.getsize(file_path) / (1024*1024):.2f} MB")

    db = SessionLocal()
    
    print("\n--- Starting Stress Test ---")
    
    # 1. Create Test Run
    print("Creating TestRun...")
    test_run = models.TestRun(status="pending")
    db.add(test_run)
    db.commit()
    db.refresh(test_run)
    run_id = test_run.id
    print(f"TestRun created with ID: {run_id}")
    
    # 2. Upload / Parse
    print(f"\n[Phase 1] Processing XML... This may take a while.")
    start_time = time.time()
    try:
        process_upload_background(file_path, run_id, db)
    except Exception as e:
        print(f"Upload failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return
    
    upload_duration = time.time() - start_time
    print(f"Upload/Parse completed in {upload_duration:.2f} seconds.")
    
    # Check stats
    db.refresh(test_run)
    print(f"Stats: Total Tests={test_run.total_tests}, Failed={test_run.failed_tests}, Modules={test_run.total_modules}")
    
    # 3. Analysis
    print(f"\n[Phase 2] Starting AI Analysis on {test_run.failed_tests} failures...")
    start_time = time.time()
    try:
        run_analysis_task(run_id, db)
    except Exception as e:
        print(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return
        
    analysis_duration = time.time() - start_time
    print(f"Analysis completed in {analysis_duration:.2f} seconds.")
    
    # Check clusters
    # Count distinct clusters
    cluster_count = db.query(models.FailureCluster).join(models.FailureAnalysis).join(models.TestCase).filter(models.TestCase.test_run_id == run_id).distinct().count()
    print(f"Total Clusters Identified: {cluster_count}")
    
    db.close()
    print("\n--- Stress Test Finished ---")

if __name__ == "__main__":
    run_stress_test()
