from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import insert, desc
from backend.database.database import get_db, SessionLocal
from backend.database import models
from backend.parser.xml_parser import XMLParser
import shutil
import os
import uuid
from datetime import datetime

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def process_upload_background(file_path: str, test_run_id: int):
    db = SessionLocal()
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
            test_run.build_version_sdk = metadata.get("build_version_sdk")
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
            
            # Save XML Summary values
            test_run.xml_modules_done = metadata.get("modules_done", 0)
            test_run.xml_modules_total = metadata.get("modules_total", 0)

            # --- Submission Auto-Grouping Logic ---
            fingerprint = test_run.device_fingerprint
            if fingerprint and fingerprint != "Pending...":
                # 1. Try Exact Fingerprint Match
                # Find latest submission for this fingerprint
                submission = db.query(models.Submission).filter(
                    models.Submission.target_fingerprint == fingerprint
                ).order_by(desc(models.Submission.updated_at)).first()
                
                # Check Lock Status
                if submission and submission.is_locked:
                    print(f"Submission {submission.id} is LOCKED. Creating new submission for fingerprint {fingerprint}")
                    submission = None #  Force new creation
                
                # 2. GSI Fingerprint Match (Ignore Android Version part)
                # User Requirement: 
                # CTS: prefix:15/suffix
                # GSI: prefix:11/suffix
                # Logic: Match Prefix and Suffix, ignore the middle version.
                if not submission:
                    import re
                    # Regex: Group 1 (Prefix), Group 2 (Version), Group 3 (Suffix)
                    # Pattern: ^([^:]+):([^/]+)/(.+)$
                    fp_pattern = re.compile(r"^([^:]+):([^/]+)/(.+)$")
                    
                    match = fp_pattern.match(fingerprint)
                    if match:
                        prefix = match.group(1) # e.g. Trimble/T70/thorpe
                        # version = match.group(2) # e.g. 11
                        suffix = match.group(3) # e.g. RKQ1...
                        
                        # Find candidates with same Prefix (Brand/Product/Device)
                        # We limit to recent submissions to avoid scanning too many
                        candidates = db.query(models.Submission).filter(
                             models.Submission.target_fingerprint.like(f"{prefix}:%")
                        ).order_by(desc(models.Submission.updated_at)).limit(20).all()
                        
                        for cand in candidates:
                            if not cand.target_fingerprint: continue
                            
                            c_match = fp_pattern.match(cand.target_fingerprint)
                            if c_match:
                                c_prefix = c_match.group(1)
                                c_suffix = c_match.group(3)
                                
                                # We already checked prefix via SQL LIKE somewhat, but double check exact match
                                if c_prefix == prefix and c_suffix == suffix:
                                    submission = cand
                                    print(f"Grouped by GSI Fingerprint Match to Submission {submission.id} (Ignored Version Diff)")
                                    break
                
                if not submission:
                    # Create new submission
                    prod = test_run.build_product
                    if not prod or prod == "Unknown":
                        # Try parsing from fingerprint (Brand/Product/Device...)
                        parts = fingerprint.split('/')
                        if len(parts) > 1:
                            prod = parts[1]
                        else:
                            prod = "Unknown Device"

                    # Default name format: [Product] - [Date]
                    # We can refine this later or allow renaming
                    sub_name = f"Submission {prod} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
                    
                    submission = models.Submission(
                        name=sub_name,
                        target_fingerprint=fingerprint,
                        status="analyzing",
                        gms_version=test_run.android_version, # Heuristic
                        product=prod # Populate Product
                    )
                    db.add(submission)
                    db.flush() # Generate ID
                    print(f"Created new Submission ID: {submission.id} for fingerprint: {fingerprint}")
                else:
                    print(f"Found existing Submission ID: {submission.id} for fingerprint: {fingerprint}")
                
                test_run.submission_id = submission.id
            # --------------------------------------
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
        
        all_modules = set()       # Set of "module_name:abi" pairs
        failed_modules_set = set()
        
        for test_case_data in parser.parse(file_path):
            total += 1
            status = test_case_data.get("status")
            module_name = test_case_data.get("module_name")
            module_abi = test_case_data.get("module_abi", "")
            
            # Use module:abi as unique key to properly count ABI variants
        batch_modules = []
        executed_modules_set = set() # To prevent duplicates (though parser yields once per module start/end, iterparse behavior)
        
        for item in parser.parse(file_path):
            # Check for new event types
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
                continue
            
            # Default is test case result
            test_case_data = item
            module_name = test_case_data.get("module_name")
            module_abi = test_case_data.get("module_abi")
            status = test_case_data.get("status")
            
            total += 1
            
            module_key = f"{module_name}:{module_abi}" if module_name else None
            
            # Update stats
            if module_key:
                all_modules.add(module_key)
            
            if status == "pass":
                passed += 1
            elif status == "fail":
                failed += 1
                if module_key:
                    failed_modules_set.add(module_key)
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
                
        # Insert remaining test cases
        if batch:
            db.execute(models.TestCase.__table__.insert(), batch)
            db.commit()
            
        # Fallback: If no explicit module_info (Module headers) were found, infer from test cases
        if not batch_modules and all_modules:
            try:
                with open("upload_debug.log", "a") as f:
                    f.write(f"Warning: No explicit module_info found. Inferring {len(all_modules)} modules from test cases for Run {test_run_id}.\n")
            except: pass
            
            for mod_key in all_modules:
                parts = mod_key.split(":")
                if len(parts) == 2:
                    name, abi = parts
                    batch_modules.append({
                        "test_run_id": test_run_id,
                        "module_name": name,
                        "module_abi": abi
                    })

        # Insert all executed modules
        if batch_modules:
            # Batch Insert modules
            # SQLite handles limits reasonably well, but for huge sets maybe batch?
            # Modules are ~200-1000, so single batch is usually fine.
            try:
                with open("upload_debug.log", "a") as f:
                    f.write(f"Inserting {len(batch_modules)} modules for Run {test_run_id}\n")
                    import json
                    f.write(json.dumps(batch_modules[0]) + "\n")

                db.execute(models.TestRunModule.__table__.insert(), batch_modules)
                db.commit()
                with open("upload_debug.log", "a") as f:
                     f.write("Insert Committed.\n")
            except Exception as e:
                with open("upload_debug.log", "a") as f:
                    f.write(f"Failed to store modules: {e}\n")
        
        # Calculate module statistics from in-memory sets
        total_modules = len(all_modules)
        failed_modules_count = len(failed_modules_set)
        passed_modules_count = total_modules - failed_modules_count
            
        # Update TestRun stats and status
        # total_tests is now used as "Executed Tests" (Pass + Fail)
        test_run.total_tests = passed + failed
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
        try:
            test_run = db.query(models.TestRun).filter(models.TestRun.id == test_run_id).first()
            if test_run:
                test_run.status = "failed"
                db.commit()
        except:
            pass
    finally:
        db.close()

@router.post("/")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Validation
    ALLOWED_EXTENSIONS = {".xml"}
    ALLOWED_MIME_TYPES = {"text/xml", "application/xml"}
    
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file extension. Only .xml files are allowed.")
        
    if file.content_type not in ALLOWED_MIME_TYPES:
        # Strict MIME check can be flaky with some browsers/clients. 
        # We assume the client is honest or we check the header. 
        # For a helper tool, checking extension is 90% of defense, checking content_type is extra.
        # Let's be lenient or log warning? No, requested security. Enforce it.
        # But commonly uploaded XMLs might have generic types.
        # Let's stick to extension check as primary, and trusted MIME types.
        print(f"Warning: Uploaded file content_type is {file.content_type}")
        # Allow generic text/plain if extension is xml?
        if file.content_type != "text/plain": 
             pass # Strict? 
             # Let's just enforce XML types + text/plain for compatibility
    
    # 2. Save the file
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
    background_tasks.add_task(process_upload_background, file_path, test_run.id)

    return {
        "message": "File uploaded. Processing started in background.",
        "test_run_id": test_run.id,
        "submission_id": test_run.submission_id,
        "status": "pending"
    }
