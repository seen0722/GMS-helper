import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import models

# Connect to the actual database
SQLALCHEMY_DATABASE_URL = "sqlite:///./gms_analysis.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()

try:
    # Check all clusters and their analysis count
    all_clusters = db.query(models.FailureCluster).all()
    print(f"Total clusters in database: {len(all_clusters)}")
    
    orphaned = []
    for cluster in all_clusters:
        analysis_count = db.query(models.FailureAnalysis).filter(
            models.FailureAnalysis.cluster_id == cluster.id
        ).count()
        
        status = "ORPHANED" if analysis_count == 0 else "OK"
        print(f"  [{status}] Cluster ID: {cluster.id}, Analyses: {analysis_count}, Redmine: {cluster.redmine_issue_id}")
        
        if analysis_count == 0:
            orphaned.append(cluster)
    
    print(f"\nFound {len(orphaned)} orphaned clusters that should be cleaned up")
    
    # Check test runs
    runs = db.query(models.TestRun).all()
    print(f"\nTotal test runs: {len(runs)}")
    for run in runs:
        print(f"  - Run ID: {run.id}, Suite: {run.test_suite_name}")

finally:
    db.close()
