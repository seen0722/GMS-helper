
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import models
from backend.parser.xml_parser import XMLParser
import os

SQLALCHEMY_DATABASE_URL = "sqlite:///./gms_analysis.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def fix_run_modules():
    print("Starting Recovery for Run 2...")
    
    # 1. Find the target run (Run with 3 modules but 0 entries in table)
    # We look for the latest run with total_modules=3
    run = db.query(models.TestRun).filter(
        models.TestRun.submission_id == 1,
        models.TestRun.total_modules == 3
    ).order_by(models.TestRun.id.desc()).first()
    
    if not run:
        print("Target Run not found.")
        return
        
    print(f"Found Run ID: {run.id}, Total Modules: {run.total_modules}")
    
    # Check if already populated
    existing = db.query(models.TestRunModule).filter(models.TestRunModule.test_run_id == run.test_run_id).count() if hasattr(models.TestRunModule, 'test_run_id') else 0
    # Correction: The model uses 'test_run_id', let's check correctly
    existing_count = db.query(models.TestRunModule).filter(models.TestRunModule.test_run_id == run.id).count()
    
    if existing_count > 0:
        print(f"Run {run.id} already has {existing_count} modules. Skipping.")
        return

    # 2. Find the file
    UPLOAD_DIR = "uploads"
    # Find latest sample_cts.xml
    files = [f for f in os.listdir(UPLOAD_DIR) if "sample_cts.xml" in f]
    if not files:
        print("No sample_cts.xml found in uploads.")
        return
        
    # Sort by modification time
    files.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_DIR, x)), reverse=True)
    target_file = os.path.join(UPLOAD_DIR, files[0])
    print(f"Using file: {target_file}")
    
    # 3. Parse and Insert
    parser = XMLParser()
    modules_to_insert = []
    seen = set()
    
    for item in parser.parse(target_file):
        if item.get("type") == "module_info":
            mod_name = item.get("module_name")
            mod_abi = item.get("module_abi")
            key = f"{mod_name}:{mod_abi}"
            if key not in seen:
                seen.add(key)
                modules_to_insert.append({
                    "test_run_id": run.id,
                    "module_name": mod_name,
                    "module_abi": mod_abi
                })
    
    if modules_to_insert:
        print(f"Inserting {len(modules_to_insert)} modules...")
        try:
            db.execute(models.TestRunModule.__table__.insert(), modules_to_insert)
            db.commit()
            print("Recovery Successful.")
        except Exception as e:
            print(f"Insert failed: {e}")
            db.rollback()
    else:
        print("No modules found in XML.")

if __name__ == "__main__":
    fix_run_modules()
