import sqlite3

def migrate():
    conn = sqlite3.connect('data/gms_analysis.db')
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(settings)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'app_base_url' not in columns:
            print("Adding app_base_url column to settings table...")
            cursor.execute("ALTER TABLE settings ADD COLUMN app_base_url VARCHAR DEFAULT 'http://localhost:8000'")
            conn.commit()
            print("Migration successful")
        else:
            print("Column app_base_url already exists")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
