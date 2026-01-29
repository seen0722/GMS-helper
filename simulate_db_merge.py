from backend.database.database import SessionLocal
from backend.database import models

def simulate_merge(run_id_base, run_id_patch):
    db = SessionLocal()
    
    # 1. Fetch Data
    # Get all executed modules for both runs
    base_modules = db.query(models.TestRunModule).filter(models.TestRunModule.test_run_id == run_id_base).all()
    patch_modules = db.query(models.TestRunModule).filter(models.TestRunModule.test_run_id == run_id_patch).all()
    
    # Get all failures for both runs
    base_failures = db.query(models.TestCase).filter(models.TestCase.test_run_id == run_id_base).all()
    patch_failures = db.query(models.TestCase).filter(models.TestCase.test_run_id == run_id_patch).all()
    
    print(f"--- Input Data ---")
    print(f"Run {run_id_base} (Base): {len(base_modules)} modules, {len(base_failures)} failures")
    print(f"Run {run_id_patch} (Patch): {len(patch_modules)} modules, {len(patch_failures)} failures")
    
    # 2. Build Maps for Efficiency
    # Failure Map: (module, class, method) -> FailureObj
    base_fail_map = {(f.module_name, f.class_name, f.method_name): f for f in base_failures}
    patch_fail_map = {(f.module_name, f.class_name, f.method_name): f for f in patch_failures}
    
    # Module Set: Set of unique module names (or name+abi)
    # Using name+abi is safer for CTS
    base_mod_set = {(m.module_name, m.module_abi) for m in base_modules}
    patch_mod_set = {(m.module_name, m.module_abi) for m in patch_modules}
    
    # 3. The Merge Logic (Algorithm)
    final_failures = []
    resolved_failures = []
    
    print(f"--- Logic Trace ---")
    
    unique_base_failures = set(base_fail_map.keys())
    unique_patch_failures = set(patch_fail_map.keys())
    
    print(f"Unique Failures in Base: {len(unique_base_failures)}")
    print(f"Unique Failures in Patch: {len(unique_patch_failures)}")
    
    # 4. detailed Merge
    final_failure_keys = set()
    
    # Analyze overlap modules
    overlapping_modules = base_mod_set.intersection(patch_mod_set)
    print(f"Overlapping Modules (Retested): {len(overlapping_modules)}")
    
    # Calculate failures in non-overlapping modules (Preserved from Base)
    preserved_failures = 0
    for key in unique_base_failures:
        mod_key = (key[0], "unknown_abi") # We don't have ABI in failure key easily unless we map it. 
        # But we can check if module_name is in overlapping_modules names.
        # Let's simplify and just use module name intersection.
        if key[0] not in [m[0] for m in overlapping_modules]:
             final_failure_keys.add(key)
             preserved_failures += 1
             
    print(f"Failures in Non-Retested Modules (Kept from Base): {preserved_failures}")
    
    # Calculate failures in overlapping modules (Taken from Patch)
    new_failures = 0
    start_failures_in_overlap = 0
    
    # Count how many were in base for these modules
    for key in unique_base_failures:
        if key[0] in [m[0] for m in overlapping_modules]:
             start_failures_in_overlap += 1
             
    print(f"Failures in Retested Modules (Found in Base): {start_failures_in_overlap} -> WILL BE REMOVED")
    
    # Add patch failures
    for key in unique_patch_failures:
        final_failure_keys.add(key)
        new_failures += 1
        
    print(f"Failures in Retested Modules (Found in Patch): {new_failures} -> WILL BE ADDED")
    
    print(f"\n--- Final Calculation ---")
    print(f"Base Total ({len(unique_base_failures)}) - Overlap Old ({start_failures_in_overlap}) + Overlap New ({new_failures}) = {len(final_failure_keys)}")
    print(f"Final Unique Failures: {len(final_failure_keys)}")

if __name__ == "__main__":
    simulate_merge(1, 2)
