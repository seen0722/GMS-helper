from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database import models
import os
import shutil


router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}


UPLOAD_DIR = "uploads"

@router.post("/reset")
def reset_data(db: Session = Depends(get_db)):
    try:
        # 1. Drop and recreate tables to handle schema changes and full reset
        from backend.database.database import engine, Base
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        
        # 2. Clear uploads directory
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}. Reason: {e}")
                    
        return {"message": "System reset successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")
