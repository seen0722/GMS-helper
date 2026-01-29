
from backend.parser.xml_parser import XMLParser
from backend.database import models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

SQLALCHEMY_DATABASE_URL = "sqlite:///./gms_analysis.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Mock Test Run
test_run_id = 9999

# File
UPLOAD_DIR = "uploads"
files = [f for f in os.listdir(UPLOAD_DIR) if "sample_cts.xml" in f]
files.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_DIR, x)), reverse=True)
target_file = os.path.join(UPLOAD_DIR, files[0])
print(f"Debug Upload on: {target_file}")

parser = XMLParser()
batch_modules = []
executed_modules_set = set()

print("Starting Parse Loop...")
for item in parser.parse(target_file):
    if "type" in item and item["type"] == "module_info":
        mod_name = item.get("module_name")
        mod_abi = item.get("module_abi")
        mod_key = f"{mod_name}:{mod_abi}"
        
        if mod_key and mod_key not in executed_modules_set:
            executed_modules_set.add(mod_key)
            batch_modules.append({
                "test_run_id": test_run_id,
                "module_name": mod_name,
                "module_abi": mod_abi
            })
        print(f"Captured Module: {mod_name}")

print(f"Total Batched Modules: {len(batch_modules)}")

if batch_modules:
    print("Attempting Insert...")
    try:
        # Don't actually commit to mess up DB, just try logic
        # But we need to verify insert works. 
        # We can rollback.
        db.execute(models.TestRunModule.__table__.insert(), batch_modules)
        print("Insert Executed Successfully.")
    except Exception as e:
        print(f"INSERT FAILED: {e}")
        import traceback
        traceback.print_exc()

db.close()
