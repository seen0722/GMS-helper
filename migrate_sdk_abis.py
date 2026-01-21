"""
Migration: Add build_version_sdk and build_abis columns to test_runs table.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "gms_analysis.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(test_runs)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "build_version_sdk" not in columns:
        print("Adding column: build_version_sdk")
        cursor.execute("ALTER TABLE test_runs ADD COLUMN build_version_sdk VARCHAR")
    else:
        print("Column build_version_sdk already exists")
    
    if "build_abis" not in columns:
        print("Adding column: build_abis")
        cursor.execute("ALTER TABLE test_runs ADD COLUMN build_abis VARCHAR")
    else:
        print("Column build_abis already exists")
    
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
