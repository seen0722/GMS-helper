import sqlite3
import os

DB_FILE = "gms_analysis.db"

def migrate():
    if not os.path.exists(DB_FILE):
        if os.path.exists(f"data/{DB_FILE}"):
            db_path = f"data/{DB_FILE}"
        else:
            print(f"Database file {DB_FILE} not found!")
            return
    else:
        db_path = DB_FILE

    print(f"Migrating database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Check test_runs columns
    print("Checking 'test_runs' table...")
    cursor.execute("PRAGMA table_info(test_runs)")
    current_run_columns = {info[1] for info in cursor.fetchall()}

    expected_run_columns = {
        "build_id": "VARCHAR",
        "build_product": "VARCHAR",
        "build_brand": "VARCHAR",
        "build_device": "VARCHAR",
        "build_model": "VARCHAR",
        "build_type": "VARCHAR",
        "security_patch": "VARCHAR",
        "android_version": "VARCHAR",
        "build_version_incremental": "VARCHAR",
        "build_version_sdk": "VARCHAR",
        "build_abis": "VARCHAR",
        "suite_version": "VARCHAR",
        "suite_plan": "VARCHAR",
        "suite_build_number": "VARCHAR",
        "host_name": "VARCHAR",
        "start_display": "VARCHAR",
        "end_display": "VARCHAR",
        "submission_id": "INTEGER REFERENCES submissions(id)"
    }

    for col, dtype in expected_run_columns.items():
        if col not in current_run_columns:
            print(f"Adding '{col}' to test_runs...")
            try:
                cursor.execute(f"ALTER TABLE test_runs ADD COLUMN {col} {dtype}")
                print(f"Added {col}.")
            except Exception as e:
                print(f"Failed to add {col}: {e}")
        else:
             print(f"Column '{col}' exists in test_runs.")
    
    # 2. Sync Submissions Table
    print("Checking 'submissions' table...")
    cursor.execute("PRAGMA table_info(submissions)")
    current_columns = {info[1] for info in cursor.fetchall()}
    
    expected_columns = {
        "product": "VARCHAR",
        "is_locked": "BOOLEAN DEFAULT 0",
        "analysis_result": "TEXT",
        "gms_version": "VARCHAR",
        "lab_name": "VARCHAR",
        "target_fingerprint": "VARCHAR",
        "brand": "VARCHAR",
        "device": "VARCHAR"
    }
    
    for col, dtype in expected_columns.items():
        if col not in current_columns:
            print(f"Adding '{col}' to submissions...")
            try:
                cursor.execute(f"ALTER TABLE submissions ADD COLUMN {col} {dtype}")
                print(f"Added {col}.")
            except Exception as e:
                print(f"Failed to add {col}: {e}")
        else:
            print(f"Column '{col}' exists.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
