
from backend.routers.upload import process_upload_background
import os

# 1. Find the file
UPLOAD_DIR = "uploads"
target_file = "uploads/b12d4290-0a44-407a-8316-aac0af7bcdf0_sample_cts.xml"

print(f"Reprocessing file: {target_file}")

# 2. Trigger Logic for Run ID 2
print("Calling process_upload_background(file, 2)...")
process_upload_background(target_file, 2)
print("Done.")

# Verify immediately
from backend.database.database import SessionLocal
from backend.database import models
db = SessionLocal()
count = db.query(models.TestRunModule).filter(models.TestRunModule.test_run_id == 2).count()
print(f"VERIFICATION: Found {count} modules for Run 2 in DB.")
db.close()
