from backend.database.database import SessionLocal
from backend.database import models

def cleanup():
    db = SessionLocal()
    orphaned_runs = db.query(models.TestRun).filter(models.TestRun.submission_id == None).all()
    if orphaned_runs:
        print(f"Found {len(orphaned_runs)} orphaned runs. Deleting...")
        for run in orphaned_runs:
            print(f"Deleting Run #{run.id}")
            db.delete(run)
        db.commit()
        print("Cleanup complete.")
    else:
        print("No orphaned runs found.")
    db.close()

if __name__ == "__main__":
    cleanup()
