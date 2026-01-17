import sqlite3
import os

DB_FILE = "gms_analysis.db"

def migrate():
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} not found!")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(test_runs)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "build_version_incremental" not in columns:
        print("Adding 'build_version_incremental' column...")
        try:
            cursor.execute("ALTER TABLE test_runs ADD COLUMN build_version_incremental VARCHAR")
            conn.commit()
            print("Migration successful.")
        except Exception as e:
            print(f"Migration failed: {e}")
    else:
        print("Column 'build_version_incremental' already exists.")

    conn.close()

if __name__ == "__main__":
    migrate()
