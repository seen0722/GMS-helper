from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import insert
from backend.database.database import get_db
from backend.database import models
from backend.parser.xml_parser import XMLParser
import shutil
import os
import uuid
from datetime import datetime

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def process_upload_background(file_path: str, test_run_id: int, db: Session):
    try:
        # Update status to processing
        test_run = db.query(models.TestRun).filter(models.TestRun.id == test_run_id).first()
        if not test_run:
            return
        
        test_run.status = "processing"
        db.commit()

        # 2. Parse Metadata
        parser = XMLParser()
        try:
            metadata = parser.get_metadata(file_path)
            test_run.test_suite_name = metadata.get("test_suite_name")
            test_run.device_fingerprint = metadata.get("device_fingerprint")
            test_run.build_id = metadata.get("build_id")
            test_run.build_product = metadata.get("build_product")
            test_run.build_model = metadata.get("build_model")
            test_run.build_type = metadata.get("build_type")
            test_run.security_patch = metadata.get("security_patch")
            test_run.android_version = metadata.get("android_version")
            test_run.build_version_incremental = metadata.get("build_version_incremental")
            test_run.suite_version = metadata.get("suite_version")
            test_run.suite_plan = metadata.get("suite_plan")
            test_run.suite_build_number = metadata.get("suite_build_number")
            test_run.host_name = metadata.get("host_name")
            test_run.start_display = metadata.get("start_display")
            test_run.end_display = metadata.get("end_display")
            
            # Parse start and end times (integers in milliseconds)
            if metadata.get("start_time"):
                try:
                    ts = int(metadata.get("start_time")) / 1000.0
                    test_run.start_time = datetime.fromtimestamp(ts)
                except Exception as e:
                    print(f"Failed to parse start_time: {e}")

            if metadata.get("end_time"):
                try:
                    ts = int(metadata.get("end_time")) / 1000.0
                    test_run.end_time = datetime.fromtimestamp(ts)
                except Exception as e:
                    print(f"Failed to parse end_time: {e}")
            db.commit()
        except Exception as e:
            print(f"Metadata parsing failed: {e}")
            
        # 4. Parse Test Cases and Stream to DB
        batch_size = 10000
        batch = []
        
        total = 0
        passed = 0
        failed = 0
        ignored = 0
        
        all_modules = set()
        failed_modules_set = set()
        
        for test_case_data in parser.parse(file_path):
            total += 1
            status = test_case_data.get("status")
            module_name = test_case_data.get("module_name")
            
            # Update stats
            if module_name:
                all_modules.add(module_name)
            
            if status == "pass":
                passed += 1
            elif status == "fail":
                failed += 1
                if module_name:
                    failed_modules_set.add(module_name)
            else:
                ignored += 1
                
            # ONLY store failures in DB
            if status == "fail":
                # Add test_run_id to data for Core Insert
                test_case_data["test_run_id"] = test_run.id
                batch.append(test_case_data)
            
            if len(batch) >= batch_size:
                db.execute(models.TestCase.__table__.insert(), batch)
                db.commit()
                batch = []
                
        # Insert remaining
        if batch:
            db.execute(models.TestCase.__table__.insert(), batch)
            db.commit()
        
        # Calculate module statistics from in-memory sets
        total_modules = len(all_modules)
        failed_modules_count = len(failed_modules_set)
        passed_modules_count = total_modules - failed_modules_count
            
        # Update TestRun stats and status
        test_run.total_tests = total
        test_run.passed_tests = passed
        test_run.failed_tests = failed
        test_run.ignored_tests = ignored
        test_run.total_modules = total_modules
        test_run.passed_modules = passed_modules_count
        test_run.failed_modules = failed_modules_count
        test_run.status = "completed"
        db.commit()
        
    except Exception as e:
        print(f"Background processing failed: {e}")
        test_run = db.query(models.TestRun).filter(models.TestRun.id == test_run_id).first()
        if test_run:
            test_run.status = "failed"
            db.commit()

@router.post("/")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Save the file
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    
    print(f"Starting upload for file: {file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    file_size = os.path.getsize(file_path)
    print(f"File saved: {file_path}, Size: {file_size} bytes")
        
    # 2. Create Initial TestRun Record
    test_run = models.TestRun(
        test_suite_name="Pending...",
        device_fingerprint="Pending...",
        start_time=datetime.utcnow(),
        status="pending"
    )
    db.add(test_run)
    db.commit()
    db.refresh(test_run)
    
    # 3. Trigger Background Task
    background_tasks.add_task(process_upload_background, file_path, test_run.id, db)

    return {
        "message": "File uploaded. Processing started in background.",
        "test_run_id": test_run.id,
        "status": "pending"
    }
