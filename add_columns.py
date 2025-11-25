import sqlite3
import time

# Wait a bit for any locks to release
time.sleep(2)

try:
    conn = sqlite3.connect('gms_analysis.db')
    cursor = conn.cursor()
    
    # Try to add each column
    columns = ['total_modules', 'passed_modules', 'failed_modules']
    for col in columns:
        try:
            cursor.execute(f"ALTER TABLE test_runs ADD COLUMN {col} INTEGER DEFAULT 0")
            print(f"Added column: {col}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column {col} already exists")
            else:
                print(f"Error adding {col}: {e}")
    
    conn.commit()
    conn.close()
    print("\nDatabase migration completed!")
    
except Exception as e:
    print(f"Error: {e}")
