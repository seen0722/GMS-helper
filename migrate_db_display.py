import sqlite3
import os

DB_FILE = "gms_analysis.db"

def migrate():
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} not found!")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if columns exist
    cursor.execute("PRAGMA table_info(test_runs)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "start_display" not in columns:
        print("Adding 'start_display' column...")
        try:
            cursor.execute("ALTER TABLE test_runs ADD COLUMN start_display VARCHAR")
            conn.commit()
            print("Added start_display.")
        except Exception as e:
            print(f"Migration start_display failed: {e}")
            
    if "end_display" not in columns:
        print("Adding 'end_display' column...")
        try:
            cursor.execute("ALTER TABLE test_runs ADD COLUMN end_display VARCHAR")
            conn.commit()
            print("Added end_display.")
        except Exception as e:
            print(f"Migration end_display failed: {e}")

    conn.close()

if __name__ == "__main__":
    migrate()
