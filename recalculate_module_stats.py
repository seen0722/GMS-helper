from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.database import models

DATABASE_URL = "sqlite:///./gms_analysis.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Get all runs with 0 module stats but have test cases
runs = session.query(models.TestRun).filter(
    models.TestRun.total_modules == 0,
    models.TestRun.total_tests > 0
).all()

print(f"Found {len(runs)} runs to update")

for run in runs:
    print(f"\nProcessing Run #{run.id}...")
    
    # Get all distinct modules
    modules_query = session.query(models.TestCase.module_name).filter(
        models.TestCase.test_run_id == run.id
    ).distinct()
    all_modules = {row[0] for row in modules_query.all()}
    
    # Get modules with failures
    failed_modules_query = session.query(models.TestCase.module_name).filter(
        models.TestCase.test_run_id == run.id,
        models.TestCase.status == "fail"
    ).distinct()
    failed_module_set = {row[0] for row in failed_modules_query.all()}
    
    total_modules = len(all_modules)
    failed_modules_count = len(failed_module_set)
    passed_modules_count = total_modules - failed_modules_count
    
    # Update the run
    run.total_modules = total_modules
    run.passed_modules = passed_modules_count
    run.failed_modules = failed_modules_count
    
    print(f"  Total Modules: {total_modules}")
    print(f"  Passed Modules: {passed_modules_count}")
    print(f"  Failed Modules: {failed_modules_count}")

session.commit()
session.close()

print("\n✅ Module statistics recalculated successfully!")
