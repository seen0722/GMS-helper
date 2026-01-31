
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.database import database, models
from backend.services.merge_service import MergeService

def debug_merge(submission_id):
    db = next(database.get_db())
    try:
        report = MergeService.get_merge_report(db, submission_id)
        
        for suite in report['suites']:
            print(f"Suite: {suite['suite_name']}")
            print(f"Run IDs: {suite['run_ids']}")
            print(f"Stats: Initial={suite['summary']['initial']}, Recovered={suite['summary']['recovered']}")
            
            if suite['suite_name'] == 'CTSonGSI':
                print("\n--- CTSonGSI Recovered Items ---")
                for item in suite['items']:
                    if item['is_recovered']:
                        print(f"Item: {item['module_name']} {item['test_class']}#{item['test_method']}")
                        print(f"History: {item['status_history']}")
                        print(f"Details: {item['failure_details'].status if item['failure_details'] else 'N/A'}")
                        print("-" * 30)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    debug_merge(1) # Hardcoded submission ID 1
