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
    # Get run ID 1
    run_id = 1
    
    # Query clusters the same way the API does
    clusters = db.query(models.FailureCluster).join(models.FailureAnalysis).join(models.TestCase).filter(
        models.TestCase.test_run_id == run_id
    ).distinct().all()
    
    print(f"Clusters for Run ID {run_id}: {len(clusters)}")
    for cluster in clusters:
        # Count failures for this run
        count = db.query(models.TestCase).join(models.FailureAnalysis).filter(
            models.TestCase.test_run_id == run_id,
            models.FailureAnalysis.cluster_id == cluster.id
        ).count()
        
        print(f"  - Cluster ID: {cluster.id}, Failures: {count}, Summary: {cluster.ai_summary[:50] if cluster.ai_summary else 'N/A'}...")

finally:
    db.close()
