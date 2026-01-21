"""
Import JSON endpoint for browser-parsed XML results.
Receives parsed test data directly, bypassing server-side XML parsing.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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


class ImportPayload(BaseModel):
    metadata: MetadataPayload
    stats: StatsPayload
    failures: List[FailurePayload]


@router.post("/")
def import_json(data: ImportPayload, db: Session = Depends(get_db)):
    """
    Import pre-parsed test results from browser.
    This endpoint receives JSON data that was parsed client-side,
    avoiding the need to upload large XML files.
    """
    try:
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
            suite_version=data.metadata.suite_version,
            suite_plan=data.metadata.suite_plan,
            suite_build_number=data.metadata.suite_build_number,
            host_name=data.metadata.host_name,
            start_time=datetime.utcnow(),  # Use current time as fallback
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

        return {
            "message": "Import successful",
            "test_run_id": test_run.id,
            "failures_imported": len(data.failures),
            "status": "completed"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
