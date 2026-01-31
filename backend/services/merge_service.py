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
                # User Requirement: 
                # If suite_name is explicitly 'CTSONGSI', or 
                # if it's 'CTS' but fingerprint differs from target, label as 'CTSonGSI'.
                if raw_name == 'CTSONGSI' or (run.device_fingerprint and sub.target_fingerprint and run.device_fingerprint != sub.target_fingerprint):
                    suite_group = 'CTSonGSI'
                else:
                    suite_group = 'CTS'
            
            if suite_group not in runs_by_suite:
                runs_by_suite[suite_group] = []
            runs_by_suite[suite_group].append(run)
            
        suites_data = []
        total_initial = 0
        total_recovered = 0
        total_remaining = 0

        for suite_name, suite_runs in runs_by_suite.items():
            summary_data = MergeService.calculate_suite_summary(db, suite_runs)
            
            suites_data.append({
                "suite_name": suite_name,
                "run_ids": [r.id for r in suite_runs],
                "runs": suite_runs,
                "total_tests": summary_data["total_tests"],
                "summary": {
                    "initial": summary_data["initial"],
                    "recovered": summary_data["recovered"],
                    "remaining": summary_data["remaining"]
                },
                "items": summary_data["items"]
            })
            
            total_initial += summary_data["initial"]
            total_recovered += summary_data["recovered"]
            total_remaining += summary_data["remaining"]

        return {
            "submission_id": sub.id,
            "submission": sub,
            "total_initial_failures": total_initial,
            "total_recovered": total_recovered,
            "remaining_failures": total_remaining,
            "suites": suites_data
        }

    @staticmethod
    def calculate_suite_summary(db: Session, suite_runs: List[models.TestRun]):
        """
        Calculate merged statistics and items for a specific group of runs (suite).
        Uses the 'Explicit Pass' logic (Option A).
        """
        if not suite_runs:
            return {
                "initial": 0, "recovered": 0, "remaining": 0,
                "items": [], "total_tests": 0
            }

        # Sort by time for historical analysis
        suite_runs.sort(key=lambda x: x.start_time)
        run_ids = [r.id for r in suite_runs]

        case_history = {}
        
        # 1. Initialize case history entries for all failures and explicit passes found in the suite
        all_result_records = db.query(models.TestCase).filter(
            models.TestCase.test_run_id.in_(run_ids)
        ).all()

        for rec in all_result_records:
            key = (rec.module_name, rec.module_abi, rec.class_name, rec.method_name)
            
            if key not in case_history:
                case_history[key] = {
                    "status_history": ["not_executed"] * len(suite_runs),
                    "failures": [None] * len(suite_runs),
                    "info": rec
                }
            
            # Find the index of the run this record belongs to
            try:
                run_idx = run_ids.index(rec.test_run_id)
                case_history[key]["status_history"][run_idx] = rec.status
                if rec.status == 'fail':
                    case_history[key]["failures"][run_idx] = rec
            except ValueError:
                continue
                
        # Analyze history
        suite_initial = 0
        suite_recovered = 0
        suite_remaining = 0
        suite_items = []
        
        for key, data in case_history.items():
            history = data["status_history"]
            
            is_initial_fail = history[0] == 'fail'
            # Recovered means: Was failing initially AND is now passing (or passed in history)
            is_recovered = is_initial_fail and ('pass' in history)
            
            if is_initial_fail:
                suite_initial += 1
            
            if is_recovered:
                suite_recovered += 1
            elif is_initial_fail and not is_recovered:
                # Started failing and never recovered
                suite_remaining += 1
            elif 'fail' in history:
                # Not initial fail, but failed later (Regression)
                suite_remaining += 1
            
            # Use the last available failure for details (if persistent)
            # or the first failure (if recovered)
            last_fail_idx = -1
            for i in range(len(history)-1, -1, -1):
                if history[i] == 'fail':
                    last_fail_idx = i
                    break
            
            representative_failure = data["failures"][last_fail_idx] if last_fail_idx != -1 else data["info"]

            # Only include items that have failed at least once (filter out purely passing items that might exist in DB)
            if 'fail' in history:
                suite_items.append({
                    "module_name": representative_failure.module_name,
                    "module_abi": representative_failure.module_abi,
                    "test_class": representative_failure.class_name,
                    "test_method": representative_failure.method_name,
                    "initial_run_id": suite_runs[0].id,
                    "final_run_id": suite_runs[-1].id,
                    "is_recovered": is_recovered,
                    "status_history": history,
                    "failure_details": representative_failure
                })
            
        # Total Tests for this suite (Executed only - aligned with UI)
        suite_total_tests = max([(r.passed_tests or 0) + (r.failed_tests or 0) for r in suite_runs]) if suite_runs else 0

        return {
            "initial": suite_initial,
            "recovered": suite_recovered,
            "remaining": suite_remaining,
            "items": suite_items,
            "total_tests": suite_total_tests
        }
