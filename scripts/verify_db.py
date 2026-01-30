import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.database import SessionLocal
from backend.database import models

db = SessionLocal()
try:
    print("--- Submissions ---")
    subs = db.query(models.Submission).all()
    for s in subs:
        print(f"ID {s.id}: {s.name}")
    
    print("\n--- Test Runs (Metadata) ---")
    runs = db.query(models.TestRun).limit(5).all()
    for r in runs:
        print(f"Run {r.id}: Brand={r.build_brand}, Model={r.build_model}, Patch={r.security_patch}")

finally:
    db.close()
