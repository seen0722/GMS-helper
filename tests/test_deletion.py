import sys
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import models
from backend.database.database import Base
from backend.routers.reports import delete_test_run

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_clean_deletion():
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    try:
        # 1. Create Data
        # Create Run
        run = models.TestRun(test_suite_name="CTS", device_fingerprint="test-device")
        db.add(run)
        db.commit()
        db.refresh(run)
        print(f"Created Run ID: {run.id}")

        # Create Test Case (Failure)
        test_case = models.TestCase(
            test_run_id=run.id,
            module_name="CtsCameraTestCases",
            class_name="CameraTest",
            method_name="testCamera",
            status="fail",
            error_message="Camera failed"
        )
        db.add(test_case)
        db.commit()
        db.refresh(test_case)
        print(f"Created Test Case ID: {test_case.id}")

        # Create Cluster
        cluster = models.FailureCluster(
            signature="camera-fail-sig",
            description="Camera failure cluster"
        )
        db.add(cluster)
        db.commit()
        db.refresh(cluster)
        print(f"Created Cluster ID: {cluster.id}")

        # Create Analysis (Link Case and Cluster)
        analysis = models.FailureAnalysis(
            test_case_id=test_case.id,
            cluster_id=cluster.id,
            root_cause="Hardware issue"
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        print(f"Created Analysis ID: {analysis.id}")

        # Verify links
        assert test_case.failure_analysis == analysis
        assert analysis.cluster == cluster
        print("Links verified.")

        # 2. Delete Run
        print("Deleting Run...")
        delete_test_run(run.id, db)

        # 3. Verify Deletion
        # Run should be gone
        deleted_run = db.query(models.TestRun).filter(models.TestRun.id == run.id).first()
        assert deleted_run is None
        print("Run deleted.")

        # Test Case should be gone (cascade)
        deleted_case = db.query(models.TestCase).filter(models.TestCase.id == test_case.id).first()
        assert deleted_case is None
        print("Test Case deleted.")

        # Analysis should be gone (cascade from Test Case)
        deleted_analysis = db.query(models.FailureAnalysis).filter(models.FailureAnalysis.id == analysis.id).first()
        assert deleted_analysis is None
        print("Analysis deleted.")

        # Cluster should be gone (orphan cleanup)
        deleted_cluster = db.query(models.FailureCluster).filter(models.FailureCluster.id == cluster.id).first()
        assert deleted_cluster is None
        print("Cluster deleted.")

        print("\nSUCCESS: Clean deletion verified!")

    finally:
        db.close()

if __name__ == "__main__":
    test_clean_deletion()
