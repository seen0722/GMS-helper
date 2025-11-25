from backend.database.database import SessionLocal
from backend.database import models

def check_failures():
    db = SessionLocal()
    try:
        # Get latest run
        run = db.query(models.TestRun).order_by(models.TestRun.id.desc()).first()
        if not run:
            print("No Test Runs found.")
            return

        print(f"Latest Run ID: {run.id}")
        print(f"Run Status: {run.status}")
        print(f"Failed Tests Count (Run Stats): {run.failed_tests}")

        # Count actual failures in TestCase table
        failures_count = db.query(models.TestCase).filter(
            models.TestCase.test_run_id == run.id,
            models.TestCase.status == "fail"
        ).count()
        
        print(f"Actual Failures in DB: {failures_count}")
        
        if failures_count > 0:
            first_failure = db.query(models.TestCase).filter(
                models.TestCase.test_run_id == run.id,
                models.TestCase.status == "fail"
            ).first()
            print(f"Sample Failure: {first_failure.module_name} - {first_failure.class_name}#{first_failure.method_name}")
            print(f"Error Message: {first_failure.error_message[:100] if first_failure.error_message else 'None'}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_failures()
