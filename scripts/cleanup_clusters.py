
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.database import database
from backend.services.analysis_service import AnalysisService

def main():
    print("Running orphan cluster cleanup...")
    db = next(database.get_db())
    try:
        count = AnalysisService.cleanup_orphan_clusters(db)
        print(f"Cleanup finished. Total removed: {count}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
