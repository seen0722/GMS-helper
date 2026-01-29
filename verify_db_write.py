from backend.database.database import SessionLocal, engine
from backend.database import models
import os

print(f"Engine URL: {engine.url}")

db = SessionLocal()
try:
    # 1. Insert Dummy Module
    print("Inserting Dummy Module...")
    dummy = {
        "test_run_id": 1,
        "module_name": "DUMMY_MODULE_TEST",
        "module_abi": "arm64"
    }
    db.execute(models.TestRunModule.__table__.insert(), [dummy])
    db.commit()
    print("Commit Executed.")
    
    # 2. Read Back via Python
    count = db.query(models.TestRunModule).filter_by(module_name="DUMMY_MODULE_TEST").count()
    print(f"Python Read: Found {count} dummy modules.")

finally:
    db.close()

# 3. Read Back via OS Command (sqlite3)
print("Checking via sqlite3 shell...")
os.system("sqlite3 gms_analysis.db \"SELECT count(*) FROM test_run_modules WHERE module_name='DUMMY_MODULE_TEST';\"")
