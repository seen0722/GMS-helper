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
    cursor.execute("PRAGMA table_info(test_runs)")
    test_run_columns = [info[1] for info in cursor.fetchall()]
    
    if "build_version_incremental" not in test_run_columns:
        print("Adding 'build_version_incremental' column to test_runs...")
        try:
            cursor.execute("ALTER TABLE test_runs ADD COLUMN build_version_incremental VARCHAR")
            print("Added build_version_incremental.")
        except Exception as e:
            print(f"Migration failed: {e}")
    
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
        "target_fingerprint": "VARCHAR"
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
