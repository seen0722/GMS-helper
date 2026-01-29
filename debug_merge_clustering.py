
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.services.merge_service import MergeService
from backend.routers.submissions import get_submission_merge_report
from backend.database import models

# Setup DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./gms_analysis.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

SUBMISSION_ID = 1

print(f"--- Debugging Merge Report for Submission {SUBMISSION_ID} ---")

# Call the service directly to check raw data
report = MergeService.get_merge_report(db, SUBMISSION_ID)
print(f"Service Report: Initial={report['total_initial_failures']}, Remaining={report['remaining_failures']}")

# Check persistent items extraction logic (replicating routes logic)
suites_response = [] 
# (Mocking the transformation logic from routes.py for brevity, or just importing the router function if possible)
# Actually, I can just call the router function if I mock the DB dependency?
# But `get_submission_merge_report` has complex transformation logic I want to test.
# I will copy the minimal logic I added to `submissions.py` here.

persistent_items = []
for suite in report["suites"]:
    for item in suite["items"]:
        if not item["is_recovered"]:
             persistent_items.append({
                "module_name": item["module_name"],
                "class_name": item["test_class"],
                "method_name": item["test_method"],
                "error_message": getattr(item["failure_details"], "error_message", "") or "",
                "stack_trace": getattr(item["failure_details"], "stack_trace", "") or ""
            })

print(f"Persistent Items Count: {len(persistent_items)}")

if persistent_items:
    from backend.analysis.clustering import ImprovedFailureClusterer
    print("Runnning Clusterer...")
    clusterer = ImprovedFailureClusterer(min_cluster_size=2)
    cluster_input = persistent_items # dict keys match
    labels, _ = clusterer.cluster_failures(cluster_input)
    print(f"Labels: {labels}")
else:
    print("No persistent items to cluster.")
