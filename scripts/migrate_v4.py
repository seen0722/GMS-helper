import sqlite3
import os

db_path = 'data/gms_analysis.db'
if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Add build_device to test_runs
    try:
        cursor.execute("ALTER TABLE test_runs ADD COLUMN build_device TEXT")
        print("Added column: test_runs.build_device")
    except sqlite3.OperationalError:
        print("Column test_runs.build_device already exists")

    # 2. Add device to submissions
    try:
        cursor.execute("ALTER TABLE submissions ADD COLUMN device TEXT")
        print("Added column: submissions.device")
    except sqlite3.OperationalError:
        print("Column submissions.device already exists")

    conn.commit()
    conn.close()
    print("Migration successful.")
except Exception as e:
    print(f"Migration failed: {e}")
