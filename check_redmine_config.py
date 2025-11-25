import os
import sys

# Add current directory to path so we can import backend modules
sys.path.append(os.getcwd())

from backend.database.database import SessionLocal
from backend.database import models
from backend.utils import encryption
from backend.integrations.redmine_client import RedmineClient

def check_redmine_config():
    print("Checking Redmine Configuration...")
    
    try:
        db = SessionLocal()
        setting = db.query(models.Settings).first()
        
        if setting:
            print("INFO: Settings record found in database")
            
            # Check URL
            if setting.redmine_url:
                print(f"PASS: Redmine URL found: {setting.redmine_url}")
            else:
                print("FAIL: Redmine URL is missing")
                
            # Check API Key
            if setting.redmine_api_key:
                print(f"INFO: Encrypted Redmine API key found (length: {len(setting.redmine_api_key)})")
                try:
                    decrypted_key = encryption.decrypt(setting.redmine_api_key)
                    print(f"PASS: Successfully decrypted Redmine API key (length: {len(decrypted_key)})")
                    
                    # Test Connection
                    if setting.redmine_url:
                        print("INFO: Testing connection to Redmine...")
                        client = RedmineClient(setting.redmine_url, decrypted_key)
                        if client.test_connection():
                            print("PASS: Connection to Redmine successful")
                        else:
                            print("FAIL: Connection to Redmine failed")
                except Exception as e:
                    print(f"FAIL: Failed to decrypt Redmine API key: {e}")
            else:
                print("FAIL: Redmine API key is missing")
        else:
            print("FAIL: No Settings record found in database")
            
        db.close()
    except Exception as e:
        print(f"FAIL: Database error: {e}")

if __name__ == "__main__":
    check_redmine_config()
