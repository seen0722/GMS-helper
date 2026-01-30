"""
Import JSON endpoint for browser-parsed XML results.
Receives parsed test data directly, bypassing server-side XML parsing.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from backend.database.database import get_db
from backend.database import models

router = APIRouter()


class MetadataPayload(BaseModel):
    test_suite_name: Optional[str] = None
    device_fingerprint: Optional[str] = None
    build_id: Optional[str] = None
    build_product: Optional[str] = None
    build_model: Optional[str] = None
    build_type: Optional[str] = None
    security_patch: Optional[str] = None
    android_version: Optional[str] = None
    build_version_sdk: Optional[str] = None
    build_abis: Optional[str] = None
    build_brand: Optional[str] = None
    build_device: Optional[str] = None
    build_version_incremental: Optional[str] = None
    suite_version: Optional[str] = None
    suite_plan: Optional[str] = None
    suite_build_number: Optional[str] = None
    host_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_display: Optional[str] = None
    end_display: Optional[str] = None


class StatsPayload(BaseModel):
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    ignored_tests: int = 0
    total_modules: int = 0
    passed_modules: int = 0
    failed_modules: int = 0
    xml_modules_done: int = 0
    xml_modules_total: int = 0


class FailurePayload(BaseModel):
    module_name: Optional[str] = None
    module_abi: Optional[str] = None
    class_name: Optional[str] = None
    method_name: Optional[str] = None
    status: str = "fail"
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None

class PassPayload(BaseModel):
    module_name: str
    module_abi: Optional[str] = None
    class_name: str
    method_name: str
    status: str = "pass"


class ModuleInfo(BaseModel):
    module_name: str
    module_abi: Optional[str] = None

class ImportPayload(BaseModel):
    metadata: MetadataPayload
    stats: StatsPayload
    failures: List[FailurePayload]
    passes: List[PassPayload] = [] # New: Explicit passes for recovery tracking
    modules: List[ModuleInfo] = [] # Optional for backward compatibility


@router.post("/")
def import_json(data: ImportPayload, db: Session = Depends(get_db)):
    """
    Import pre-parsed test results from browser.
    This endpoint receives JSON data that was parsed client-side,
    avoiding the need to upload large XML files.
    """
    try:
        # --- Duplicate Check ---
        # Criteria: Same Device Fingerprint AND Same Start Time (Display or Timestamp)
        fingerprint = data.metadata.device_fingerprint
        start_display = data.metadata.start_display
        
        if fingerprint and fingerprint != "Unknown":
            query = db.query(models.TestRun).filter(
                models.TestRun.device_fingerprint == fingerprint
            )
            
            # Prefer start_display as it's a direct string from XML (e.g. "2024-01-25 10:00:00")
            if start_display:
                query = query.filter(models.TestRun.start_display == start_display)
                existing = query.first()
                if existing:
                    raise HTTPException(status_code=409, detail=f"Duplicate upload: Test run started at {start_display} already exists (Run #{existing.id}).")
            
        # -----------------------

        # Parse real start time if available
        real_start_time = datetime.utcnow()
        if data.metadata.start_time:
             try:
                 # Attempt parsed from integer timestamp (seconds or ms) or string
                 # XML usually provides seconds (epoch)
                 ts = float(data.metadata.start_time)
                 # Heuristic: if > 30000000000, probably ms
                 if ts > 30000000000: ts /= 1000
                 real_start_time = datetime.fromtimestamp(ts)
             except:
                 pass # Fallback to utcnow

        # Create TestRun record
        test_run = models.TestRun(
            test_suite_name=data.metadata.test_suite_name or "Unknown",
            device_fingerprint=data.metadata.device_fingerprint or "Unknown",
            build_id=data.metadata.build_id,
            build_product=data.metadata.build_product,
            build_model=data.metadata.build_model,
            build_type=data.metadata.build_type,
            security_patch=data.metadata.security_patch,
            android_version=data.metadata.android_version,
            build_version_sdk=data.metadata.build_version_sdk,
            build_abis=data.metadata.build_abis,
            build_brand=data.metadata.build_brand,
            build_device=data.metadata.build_device,
            build_version_incremental=data.metadata.build_version_incremental,
            suite_version=data.metadata.suite_version,
            suite_plan=data.metadata.suite_plan,
            suite_build_number=data.metadata.suite_build_number,
            host_name=data.metadata.host_name,
            start_time=real_start_time,
            start_display=data.metadata.start_display,
            end_display=data.metadata.end_display,
            total_tests=data.stats.total_tests,
            passed_tests=data.stats.passed_tests,
            failed_tests=data.stats.failed_tests,
            ignored_tests=data.stats.ignored_tests,
            total_modules=data.stats.total_modules,
            passed_modules=data.stats.passed_modules,
            failed_modules=data.stats.failed_modules,
            xml_modules_done=data.stats.xml_modules_done,
            xml_modules_total=data.stats.xml_modules_total,
            status="completed"
        )
        
        db.add(test_run)
        db.commit()
        db.refresh(test_run)

        # --- Submission Auto-Grouping Logic ---
        from backend.services.submission_service import SubmissionService
        
        fingerprint = data.metadata.device_fingerprint
        if fingerprint and fingerprint != "Unknown":
            submission = SubmissionService.get_or_create_submission(
                db=db,
                fingerprint=fingerprint,
                suite_name=data.metadata.test_suite_name or "Unknown",
                suite_plan=data.metadata.suite_plan,
                android_version=data.metadata.android_version,
                build_product=data.metadata.build_product,
                build_brand=data.metadata.build_brand,
                build_model=data.metadata.build_model,
                build_device=data.metadata.build_device,
                security_patch=data.metadata.security_patch
            )
            test_run.submission_id = submission.id
            db.commit()
        # --------------------------------------

        # Insert Executed Modules (CRITICAL for Partial Retry Logic)
        if data.modules:
            try:
                module_records = [
                    {
                        "test_run_id": test_run.id,
                        "module_name": m.module_name,
                        "module_abi": m.module_abi
                    }
                    for m in data.modules
                ]
                db.execute(models.TestRunModule.__table__.insert(), module_records)
                db.commit()
            except Exception as e:
                print(f"Warning: Failed to insert modules: {e}")
                # Don't fail the whole import, but log it


        # Bulk insert failures
        if data.failures:
            failure_records = [
                {
                    "test_run_id": test_run.id,
                    "module_name": f.module_name,
                    "module_abi": f.module_abi,
                    "class_name": f.class_name,
                    "method_name": f.method_name,
                    "status": f.status,
                    "error_message": f.error_message,
                    "stack_trace": f.stack_trace
                }
                for f in data.failures
            ]
            db.execute(models.TestCase.__table__.insert(), failure_records)
            db.commit()

        # Insert Relevant Passes (Option A: Explicit Recovery)
        # We only store passes that match a previous failure in the same submission
        if test_run.submission_id and data.passes:
            try:
                # 1. Identify all previous failures in this submission (to filter relevant passes)
                previous_failures = db.query(models.TestCase).join(models.TestRun).filter(
                    models.TestRun.submission_id == test_run.submission_id,
                    models.TestRun.id != test_run.id,
                    models.TestCase.status == 'fail'
                ).all()
                
                if previous_failures:
                    # Create a set of keys for fast lookup
                    fail_keys = set()
                    for pf in previous_failures:
                        fail_keys.add((pf.module_name, pf.module_abi, pf.class_name, pf.method_name))
                    
                    # 2. Filter incoming passes
                    relevant_passes = []
                    for ps in data.passes:
                        key = (ps.module_name, ps.module_abi, ps.class_name, ps.method_name)
                        if key in fail_keys:
                            relevant_passes.append({
                                "test_run_id": test_run.id,
                                "module_name": ps.module_name,
                                "module_abi": ps.module_abi,
                                "class_name": ps.class_name,
                                "method_name": ps.method_name,
                                "status": "pass"
                            })
                    
                    # 3. Bulk insert
                    if relevant_passes:
                        # Optimization: Deduplicate if the same test passed multiple times in the same XML (rare but possible)
                        # We use a dict to keep only one per key
                        unique_relevant = { (p["module_name"], p["module_abi"], p["class_name"], p["method_name"]): p for p in relevant_passes }
                        db.execute(models.TestCase.__table__.insert(), list(unique_relevant.values()))
                        db.commit()
            except Exception as e:
                print(f"Warning: Failed to process explicit passes: {e}")
                db.rollback()

        return {
            "message": "Import successful",
            "test_run_id": test_run.id,
            "submission_id": test_run.submission_id,
            "failures_imported": len(data.failures),
            "modules_tracked": len(data.modules),
            "status": "completed"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
