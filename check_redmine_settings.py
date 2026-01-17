from backend.database.database import SessionLocal
from backend.models.settings import Setting, SettingType

def check_settings():
    db = SessionLocal()
    try:
        url = db.query(Setting).filter(Setting.key == "redmine_url").first()
        api_key = db.query(Setting).filter(Setting.key == "redmine_api_key").first()
        
        print("\n--- DB Settings Check ---")
        print(f"Redmine URL: {url.value if url else 'MISSING'}")
        print(f"Redmine API Key: {'[PRESENT]' if api_key and api_key.value else 'MISSING/EMPTY'}")
        if api_key:
             print(f"API Key Length: {len(api_key.value)}")
        print("-------------------------\n")
    except Exception as e:
        print(f"Error checking settings: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_settings()
