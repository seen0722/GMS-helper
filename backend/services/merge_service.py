from sqlalchemy.orm import Session
from sqlalchemy import asc
from backend.database import models
from typing import List, Dict, Any

class MergeService:
    @staticmethod
    def get_merge_report(db: Session, submission_id: int):
        sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
        if not sub:
            return None
            
        runs = db.query(models.TestRun).filter(
            models.TestRun.submission_id == submission_id
        ).order_by(asc(models.TestRun.start_time)).all()
        
        if not runs:
            return {
                "submission_id": sub.id,
                "total_initial_failures": 0,
                "total_recovered": 0,
                "remaining_failures": 0,
                "suites": []
            }

        # Group runs by derived suite name
        runs_by_suite = {}
        for run in runs:
            raw_name = (run.test_suite_name or "Unknown").upper()
            
            # Default to raw name
            suite_group = raw_name
            
            # Detect CTSonGSI logic
            if 'CTS' in raw_name:
                # Check fingerprint
                if run.device_fingerprint != sub.target_fingerprint:
                    suite_group = 'CTSonGSI'
                else:
                    suite_group = 'CTS' # Normalize to CTS
            
            if suite_group not in runs_by_suite:
                runs_by_suite[suite_group] = []
            runs_by_suite[suite_group].append(run)
            
        suites_data = []
        total_initial = 0
        total_recovered = 0
        total_remaining = 0

        for suite, suite_runs in runs_by_suite.items():
            # Get all failures for these runs
            run_ids = [r.id for r in suite_runs]
            
            case_history = {}
            
            for i, run in enumerate(suite_runs):
                failures = db.query(models.TestCase).filter(
                    models.TestCase.test_run_id == run.id,
                    models.TestCase.status == 'fail'
                ).all()
                
                # Mark failures for this run
                for f in failures:
                    key = (f.module_name, f.class_name, f.method_name)
                    
                    if key not in case_history:
                        # Initialize history as list of objects or statuses
                        # For now, simplistic status list: ["pass", "pass", ...]
                        case_history[key] = {
                            "status_history": ["pass"] * len(suite_runs),
                            "failures": [None] * len(suite_runs), # Store Failure Object for details (msg, stack)
                            "info": f # Keep one reference for metadata
                        }
                    
                    case_history[key]["status_history"][i] = "fail"
                    case_history[key]["failures"][i] = f
                    
            # Analyze history
            suite_initial = 0
            suite_recovered = 0
            suite_remaining = 0
            
            suite_items = []
            
            for key, data in case_history.items():
                history = data["status_history"]
                
                is_initial_fail = history[0] == 'fail'
                final_status = history[-1]
                is_recovered = final_status == 'pass'
                
                if is_initial_fail:
                    suite_initial += 1
                
                if is_recovered:
                     suite_recovered += 1
                else:
                     suite_remaining += 1
                
                # Use the last available failure for details (if persistent)
                # or the first failure (if recovered)
                last_fail_idx = -1
                for i in range(len(history)-1, -1, -1):
                    if history[i] == 'fail':
                        last_fail_idx = i
                        break
                
                representative_failure = data["failures"][last_fail_idx] if last_fail_idx != -1 else data["info"]

                suite_items.append({
                    "module_name": representative_failure.module_name,
                    "test_class": representative_failure.class_name,
                    "test_method": representative_failure.method_name,
                    "initial_run_id": suite_runs[0].id,
                    "final_run_id": suite_runs[-1].id,
                    "is_recovered": is_recovered,
                    "status_history": history,
                    "failure_details": representative_failure # Passed back for Excel usage (error msg, stack trace)
                })
                
            suites_data.append({
                "suite_name": suite,
                "run_ids": run_ids,
                "runs": suite_runs, # Add run objects for reference
                "summary": {
                    "initial": suite_initial,
                    "recovered": suite_recovered,
                    "remaining": suite_remaining
                },
                "items": suite_items
            })
            
            total_initial += suite_initial
            total_recovered += suite_recovered
            total_remaining += suite_remaining

        return {
            "submission_id": sub.id,
            "submission": sub,
            "total_initial_failures": total_initial,
            "total_recovered": total_recovered,
            "remaining_failures": total_remaining,
            "suites": suites_data
        }
