import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import models
from backend.database.database import Base

# Connect to the actual database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_results.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()

try:
    # Check for orphaned clusters
    orphaned_clusters = db.query(models.FailureCluster).filter(~models.FailureCluster.analyses.any()).all()
    
    print(f"Found {len(orphaned_clusters)} orphaned clusters:")
    for cluster in orphaned_clusters:
        print(f"  - Cluster ID: {cluster.id}, Signature: {cluster.signature[:50]}..., Redmine: {cluster.redmine_issue_id}")
    
    # Check all clusters and their analysis count
    all_clusters = db.query(models.FailureCluster).all()
    print(f"\nTotal clusters in database: {len(all_clusters)}")
    for cluster in all_clusters:
        analysis_count = db.query(models.FailureAnalysis).filter(models.FailureAnalysis.cluster_id == cluster.id).count()
        print(f"  - Cluster ID: {cluster.id}, Analyses: {analysis_count}, Redmine: {cluster.redmine_issue_id}")

finally:
    db.close()
