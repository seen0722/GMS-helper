from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database import models
from backend.utils import encryption
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class APIKeyUpdate(BaseModel):
    api_key: str

class RedmineSettingsUpdate(BaseModel):
    url: str
    api_key: str


def get_or_create_settings(db: Session) -> models.Settings:
    settings = db.query(models.Settings).first()
    if not settings:
        settings = models.Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/openai-key")
def get_openai_key(show_full: bool = False, db: Session = Depends(get_db)):
    """Get the OpenAI API key. By default returns masked version, set show_full=true for full key."""
    settings = get_or_create_settings(db)
    
    if not settings.openai_api_key:
        return {"masked_key": None, "is_set": False}
    
    try:
        decrypted = encryption.decrypt(settings.openai_api_key)
        
        if show_full:
            # Return full key when requested
            return {"full_key": decrypted, "is_set": True}
        else:
            # Mask all but last 4 characters
            if len(decrypted) > 4:
                masked = "*" * (len(decrypted) - 4) + decrypted[-4:]
            else:
                masked = "*" * len(decrypted)
            
            return {"masked_key": masked, "is_set": True}
    except Exception as e:
        print(f"Error decrypting API key: {e}")
        return {"masked_key": None, "is_set": False, "error": "Decryption failed"}


@router.put("/openai-key")
def update_openai_key(data: APIKeyUpdate, db: Session = Depends(get_db)):
    """Update the OpenAI API key (encrypts before storing)."""
    if not data.api_key or not data.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    
    try:
        encrypted = encryption.encrypt(data.api_key.strip())
        
        settings = get_or_create_settings(db)
        settings.openai_api_key = encrypted
        db.commit()
        
        return {"message": "API key updated successfully"}
    except Exception as e:
        db.rollback()
        print(f"Error saving API key: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save API key: {str(e)}")


@router.delete("/openai-key")
def delete_openai_key(db: Session = Depends(get_db)):
    """Delete the stored OpenAI API key."""
    settings = get_or_create_settings(db)
    settings.openai_api_key = None
    db.commit()
    
    return {"message": "API key deleted successfully"}


@router.get("/redmine")
def get_redmine_settings(show_full: bool = False, db: Session = Depends(get_db)):
    """Get Redmine settings."""
    settings = get_or_create_settings(db)
    
    if not settings.redmine_url or not settings.redmine_api_key:
        return {"url": None, "masked_key": None, "is_set": False}
    
    try:
        decrypted_key = encryption.decrypt(settings.redmine_api_key)
        
        if show_full:
            return {"url": settings.redmine_url, "full_key": decrypted_key, "is_set": True}
        else:
            if len(decrypted_key) > 4:
                masked = "*" * (len(decrypted_key) - 4) + decrypted_key[-4:]
            else:
                masked = "*" * len(decrypted_key)
            return {"url": settings.redmine_url, "masked_key": masked, "is_set": True}
            
    except Exception as e:
        print(f"Error decrypting Redmine key: {e}")
        return {"url": settings.redmine_url, "masked_key": None, "is_set": False, "error": "Decryption failed"}


@router.put("/redmine")
def update_redmine_settings(data: RedmineSettingsUpdate, db: Session = Depends(get_db)):
    """Update Redmine settings."""
    if not data.url or not data.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    if not data.api_key or not data.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")
        
    try:
        encrypted_key = encryption.encrypt(data.api_key.strip())
        
        settings = get_or_create_settings(db)
        settings.redmine_url = data.url.strip()
        settings.redmine_api_key = encrypted_key
        db.commit()
        
        return {"message": "Redmine settings updated successfully"}
    except Exception as e:
        db.rollback()
        print(f"Error saving Redmine settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save Redmine settings: {str(e)}")
