import sqlite3
import os

DB_PATH = "gms_analysis.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(test_runs)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "analysis_status" not in columns:
            print("Adding analysis_status column to test_runs table...")
            cursor.execute("ALTER TABLE test_runs ADD COLUMN analysis_status VARCHAR DEFAULT 'pending'")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column analysis_status already exists.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
