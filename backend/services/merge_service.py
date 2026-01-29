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

        for suite, suite_runs in runs_by_suite.items():
            # Get all failures for these runs
            run_ids = [r.id for r in suite_runs]
            
            # Pre-fetch executed modules for each run (for Module-Level Verification)
            # Map: run_id -> set(module_names)
            run_modules_map = {}
            for r in suite_runs:
                # Eager load/check executed modules
                # Note: executed_modules relationship must be available (lazy load ok since db session is active)
                # Force explicit query to bypass relationship caching/lazy loading issues
                mods = db.query(models.TestRunModule).filter(models.TestRunModule.test_run_id == r.id).all()
                
                try:
                    print(f"MergeService DEBUG: Run {r.id} query...")
                    with open("merge_debug_v2.log", "a") as f:
                         f.write(f"Run {r.id}: Found {len(mods)} modules via direct query.\n")
                         f.write(f"DB Engine: {str(db.get_bind().url)}\n")
                         
                         # RAW SQL CHECK
                         from sqlalchemy import text
                         result = db.execute(text("SELECT count(*) FROM test_run_modules WHERE test_run_id = :rid"), {"rid": r.id}).scalar()
                         f.write(f"RAW SQL COUNT for Run {r.id}: {result}\n")
                         
                         # Check Run Metadata
                         run_meta = db.execute(text("SELECT total_modules FROM test_runs WHERE id = :rid"), {"rid": r.id}).scalar()
                         f.write(f"Run {r.id} total_modules column: {run_meta}\n")
                except Exception as e:
                     print(f"MergeService DEBUG ERROR: {e}")
                     with open("merge_debug_v2.log", "a") as f:
                         f.write(f"Debug Log Error: {e}\n")

                if mods:
                    run_modules_map[r.id] = set(m.module_name for m in mods)
                else:
                    # STRICT MODE: If no modules found, it means we don't know what ran.
                    # We should NOT assume they passed. Treat as empty set.
                    run_modules_map[r.id] = set() 
                    print(f"DEBUG: Run {r.id} has NO executed modules. Treated as Not Executed.")

            case_history = {}
            
            for i, run in enumerate(suite_runs):
                failures = db.query(models.TestCase).filter(
                    models.TestCase.test_run_id == run.id,
                    models.TestCase.status == 'fail'
                ).all()
                
                # Mark failures for this run
                for f in failures:
                    key = (f.module_name, f.module_abi, f.class_name, f.method_name)
                    
                    if key not in case_history:
                        # Initialize history based on Module Execution Status
                        init_history = []
                        for r_check in suite_runs:
                             # Check if this module was executed in r_check
                             ctx_modules = run_modules_map.get(r_check.id, set())

                             if f.module_name in ctx_modules:
                                 # Module executed, default to pass (will be overwritten if failure found)
                                 init_history.append("pass")
                             else:
                                 # Module NOT executed in this run
                                 init_history.append("not_executed")
                        
                        case_history[key] = {
                            "status_history": init_history,
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
                # Modified Logic (User Request + Safety): 
                # If a test passed in ANY run, consider it "Recovered".
                # BUT "pass" now strictly implies "Module was executed and passed".
                # "not_executed" is NOT "pass".
                is_recovered = 'pass' in history
                
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
                    "module_abi": representative_failure.module_abi,
                    "test_class": representative_failure.class_name,
                    "test_method": representative_failure.method_name,
                    "initial_run_id": suite_runs[0].id,
                    "final_run_id": suite_runs[-1].id,
                    "is_recovered": is_recovered,
                    "status_history": history,
                    "failure_details": representative_failure # Passed back for Excel usage (error msg, stack trace)
                })
                
            # Total Tests for this suite (Executed only - aligned with UI)
            suite_total_tests = max([(r.passed_tests or 0) + (r.failed_tests or 0) for r in suite_runs]) if suite_runs else 0

            suites_data.append({
                "suite_name": suite,
                "run_ids": run_ids,
                "runs": suite_runs, # Add run objects for reference
                "total_tests": suite_total_tests,
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
