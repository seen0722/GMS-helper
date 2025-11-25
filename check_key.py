from backend.database.database import SessionLocal
from backend.database import models
from backend.utils import encryption
import os

def check_key():
    print(f"Checking for API Key...")
    
    # Check Env
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        print(f"Found OPENAI_API_KEY in env: {env_key[:5]}...{env_key[-4:]}")
    else:
        print("OPENAI_API_KEY not found in env.")

    # Check DB
    try:
        db = SessionLocal()
        setting = db.query(models.Settings).first()
        if setting:
            print("Settings record found.")
            if setting.openai_api_key:
                print("Encrypted key found in DB.")
                try:
                    decrypted = encryption.decrypt(setting.openai_api_key)
                    print(f"Decrypted key: {decrypted[:5]}...{decrypted[-4:]}")
                except Exception as e:
                    print(f"Decryption failed: {e}")
            else:
                print("openai_api_key column is empty.")
        else:
            print("No Settings record found in DB.")
        db.close()
    except Exception as e:
        print(f"DB Error: {e}")

if __name__ == "__main__":
    check_key()
