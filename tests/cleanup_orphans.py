"""
Cleanup script to remove orphaned clusters and analysis records.
Run this to clean up the database after deleting test runs.
"""
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
    print("=== Database Cleanup ===\n")
    
    # Step 1: Find and delete orphaned FailureAnalysis records (test_case_id points to non-existent test case)
    print("Step 1: Checking for orphaned FailureAnalysis records...")
    all_analyses = db.query(models.FailureAnalysis).all()
    orphaned_analyses = []
    
    for analysis in all_analyses:
        test_case = db.query(models.TestCase).filter(models.TestCase.id == analysis.test_case_id).first()
        if not test_case:
            orphaned_analyses.append(analysis)
    
    print(f"Found {len(orphaned_analyses)} orphaned FailureAnalysis records")
    if orphaned_analyses:
        for analysis in orphaned_analyses:
            print(f"  - Deleting FailureAnalysis ID {analysis.id} (test_case_id: {analysis.test_case_id}, cluster_id: {analysis.cluster_id})")
            db.delete(analysis)
        db.commit()
        print("✓ Deleted orphaned FailureAnalysis records\n")
    
    # Step 2: Find and delete orphaned clusters (no analyses pointing to them)
    print("Step 2: Checking for orphaned FailureCluster records...")
    all_clusters = db.query(models.FailureCluster).all()
    orphaned_clusters = []
    
    for cluster in all_clusters:
        analysis_count = db.query(models.FailureAnalysis).filter(
            models.FailureAnalysis.cluster_id == cluster.id
        ).count()
        if analysis_count == 0:
            orphaned_clusters.append(cluster)
    
    print(f"Found {len(orphaned_clusters)} orphaned FailureCluster records")
    if orphaned_clusters:
        for cluster in orphaned_clusters:
            print(f"  - Deleting FailureCluster ID {cluster.id} (Redmine: {cluster.redmine_issue_id})")
            db.delete(cluster)
        db.commit()
        print("✓ Deleted orphaned FailureCluster records\n")
    
    # Step 3: Summary
    print("=== Cleanup Complete ===")
    remaining_clusters = db.query(models.FailureCluster).count()
    remaining_analyses = db.query(models.FailureAnalysis).count()
    remaining_runs = db.query(models.TestRun).count()
    
    print(f"Remaining test runs: {remaining_runs}")
    print(f"Remaining clusters: {remaining_clusters}")
    print(f"Remaining analyses: {remaining_analyses}")

finally:
    db.close()
