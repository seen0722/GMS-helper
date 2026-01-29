
from sqlalchemy import create_engine
from backend.services.merge_service import MergeService
from backend.database.database import SessionLocal, SQLALCHEMY_DATABASE_URL
from backend.database import models

# Re-create engine with echo=True for debugging
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)
db = SessionLocal()
# Bind this session to the echo engine? 
# SessionLocal is bound to the original engine in database.py.
# We need to manually construct a session with the echo engine if we want to see logs.
from sqlalchemy.orm import sessionmaker
DebugSession = sessionmaker(bind=engine)
db = DebugSession()

print("Checking Submission 1...")
sub = db.query(models.Submission).filter(models.Submission.id == 1).first()
if sub:
    print(f"Submission Found: {sub.name}")
    print("Calling MergeService...")
    report = MergeService.get_merge_report(db, 1)
    if report:
        print("Report Generated.")
    else:
        print("Report is None.")
else:
    print("Submission NOT Found in Python Session.")

print("\n--- Inspecting TestRuns directly ---")
runs = db.query(models.TestRun).filter(models.TestRun.submission_id == 1).all()
print(f"Found {len(runs)} runs.")
for r in runs:
    print(f"Run {r.id}: Total Modules (Col)={r.total_modules}")
    # Force relationship load
    mods = r.executed_modules
    print(f"  -> Executed Modules (Rel) Loaded: {len(mods) if mods else 0}")
    if not mods and r.total_modules > 0:
        print("  [WARNING] Mismatch! verifying raw table...")
        # Check raw table
        raw_count = db.execute(models.TestRunModule.__table__.select().where(models.TestRunModule.test_run_id == r.id)).fetchall()
        print(f"  [RAW] Count in test_run_modules: {len(raw_count)}")

db.close()
