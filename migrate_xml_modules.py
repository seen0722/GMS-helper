"""
Migration: Add xml_modules_done and xml_modules_total columns to test_runs table.
Run this script once to add the new columns.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "gms_analysis.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(test_runs)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "xml_modules_done" not in columns:
        print("Adding column: xml_modules_done")
        cursor.execute("ALTER TABLE test_runs ADD COLUMN xml_modules_done INTEGER DEFAULT 0")
    else:
        print("Column xml_modules_done already exists")
    
    if "xml_modules_total" not in columns:
        print("Adding column: xml_modules_total")
        cursor.execute("ALTER TABLE test_runs ADD COLUMN xml_modules_total INTEGER DEFAULT 0")
    else:
        print("Column xml_modules_total already exists")
    
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
