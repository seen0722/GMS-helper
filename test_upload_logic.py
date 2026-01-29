import os
import sys
from backend.database.database import SessionLocal, engine
from backend.database import models
from backend.routers.upload import process_upload_background

# Real User Files
REAL_FILE_1 = "reports/test_result_1.xml"
REAL_FILE_2 = "reports/test_result_2.xml"

# Test Run 2 (Partial)
TEST_FILE = REAL_FILE_2
RUN_ID = 2

if not os.path.exists(TEST_FILE):
    print(f"Error: File {TEST_FILE} not found!")
    sys.exit(1)

print(f"Testing Parser on {TEST_FILE} for Run {RUN_ID}...")

# Run Logic
try:
    process_upload_background(TEST_FILE, RUN_ID)
except Exception as e:
    print(f"Process Failed: {e}")

# Verify
db = SessionLocal()
mod_count = db.query(models.TestRunModule).filter(models.TestRunModule.test_run_id == RUN_ID).count()
print(f"VERIFICATION: Found {mod_count} modules for Run {RUN_ID}.")

if mod_count > 1000:
    print("SUCCESS: Found expected large number of modules.")
else:
    print(f"FAILURE: Expected >1000 modules, found {mod_count}.")

db.close()
