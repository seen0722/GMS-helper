
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from backend.database import models
from backend.routers.reports import _aggregate_submission_failures

# Setup DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./gms_analysis.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

SUBMISSION_ID = 1

print(f"--- Debugging Clusters for Submission {SUBMISSION_ID} ---")

# 1. Aggregate Failures
failures = _aggregate_submission_failures(db, SUBMISSION_ID)
print(f"Total Persistent Failures: {len(failures)}")

if not failures:
    print("No failures found.")
    exit()

# 2. Simulate Clustering Logic (from reports.py)
clusters = {}
for f in failures:
    # Create a signature based on Module + Error Message (first 100 chars)
    sig = f"{f['module']}::{f['error'][:100]}" 
    if sig not in clusters:
        clusters[sig] = {
            'count': 0,
            'module': f['module'],
            'error': f['error'],
            'example_test': f['test']
        }
    clusters[sig]['count'] += 1

sorted_clusters = sorted(clusters.values(), key=lambda x: x['count'], reverse=True)

print(f"Total Clusters Formed: {len(sorted_clusters)}")
print("\n--- Detailed Cluster List ---")
for i, c in enumerate(sorted_clusters):
    print(f"Cluster #{i+1} (Count: {c['count']})")
    print(f"  Module: {c['module']}")
    print(f"  Error: {c['error'][:100]}...")
