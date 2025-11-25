import os
import sys

# Add current directory to path so we can import backend modules
sys.path.append(os.getcwd())

from backend.database.database import SessionLocal
from backend.database import models
from backend.utils import encryption

def check_config():
    print("Checking LLM Configuration...")
    
    # 1. Check Environment Variable
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        print(f"PASS: OPENAI_API_KEY found in environment (length: {len(env_key)})")
    else:
        print("FAIL: OPENAI_API_KEY NOT found in environment")

    # 2. Check Database
    try:
        db = SessionLocal()
        setting = db.query(models.Settings).first()
        if setting:
            print("INFO: Settings record found in database")
            if setting.openai_api_key:
                print(f"INFO: Encrypted API key found in database (length: {len(setting.openai_api_key)})")
                try:
                    decrypted_key = encryption.decrypt(setting.openai_api_key)
                    print(f"PASS: Successfully decrypted database API key (length: {len(decrypted_key)})")
                except Exception as e:
                    print(f"FAIL: Failed to decrypt database API key: {e}")
            else:
                print("FAIL: openai_api_key column is empty in database")
        else:
            print("FAIL: No Settings record found in database")
        db.close()
    except Exception as e:
        print(f"FAIL: Database error: {e}")

if __name__ == "__main__":
    check_config()
