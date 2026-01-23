from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from backend.database.database import get_db
from backend.database import models
import pandas as pd
from io import BytesIO
from datetime import datetime

router = APIRouter()

@router.get("/submission/{submission_id}/excel")
def export_submission_excel(submission_id: int, db: Session = Depends(get_db)):
    """Export submission details to Excel (xlsx)."""
    
    # 1. Fetch Data
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    runs = db.query(models.TestRun).filter(models.TestRun.submission_id == submission_id).all()
    
    # Fetch failures with details
    failures = db.query(models.TestCase).join(models.TestRun).filter(
        models.TestRun.submission_id == submission_id,
        models.TestCase.status == 'fail'
    ).options(
        joinedload(models.TestCase.test_run),
        joinedload(models.TestCase.failure_analysis)
    ).all()
    
    # 2. Create DataFrames
    
    # A. Summary Sheet
    summary_data = {
        "ID": [sub.id],
        "Name": [sub.name],
        "Status": [sub.status],
        "GMS Version": [sub.gms_version],
        "Target Fingerprint": [sub.target_fingerprint],
        "Created At": [sub.created_at],
        "Updated At": [sub.updated_at],
        "Total Runs": [len(runs)],
        "Total Failures": [sum(r.failed_tests or 0 for r in runs)]
    }
    df_summary = pd.DataFrame(summary_data)
    
    # B. Test Runs Sheet
    runs_data = []
    for r in runs:
        runs_data.append({
            "Run ID": r.id,
            "Suite": "CTSonGSI" if (r.test_suite_name == "CTS" and "gsi" in (r.build_product or "").lower()) else r.test_suite_name,
            "Device": f"{r.build_model or ''} ({r.build_product or ''})".strip(),
            "Build Fingerprint": r.device_fingerprint,
            "Security Patch": r.security_patch,
            "Total Tests": (r.passed_tests or 0) + (r.failed_tests or 0),
            "Passed": r.passed_tests,
            "Failed": r.failed_tests,
            "Host": r.host_name,
            "Start Time": r.start_time
        })
    df_runs = pd.DataFrame(runs_data)
    
    # C. Failures Sheet
    failures_data = []
    for f in failures:
        analysis = f.failure_analysis if f.failure_analysis else None
        failures_data.append({
            "Run ID": f.test_run_id,
            "Suite": "CTSonGSI" if (f.test_run.test_suite_name == "CTS" and "gsi" in (f.test_run.build_product or "").lower()) else f.test_run.test_suite_name,
            "Module": f.module_name,
            "Test Case": f"{f.class_name}#{f.method_name}",
            "Status": f.status,
            "Failure Message": f.error_message,
            "Stacktrace": f.stack_trace[:500] if f.stack_trace else "", # Truncate for excel
            "AI Analysis": analysis.root_cause if analysis else "Pending",
            "Details": analysis.suggested_solution if analysis else ""
        })
    df_failures = pd.DataFrame(failures_data)
    
    # 3. Write to Excel Buffer
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        df_runs.to_excel(writer, sheet_name='Test Runs', index=False)
        df_failures.to_excel(writer, sheet_name='Failures', index=False)
        
        # Auto-adjust columns (basic)
        for worksheet in writer.sheets.values():
            for column_cells in worksheet.columns:
                length = max(len(str(cell.value)) for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)
                
    output.seek(0)
    
    # 4. Stream Response
    filename = f"submission_{sub.id}_{sub.name.replace(' ', '_')}.xlsx"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    
    return StreamingResponse(
        output, 
        headers=headers, 
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
