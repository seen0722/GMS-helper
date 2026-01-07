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


class LLMProviderUpdate(BaseModel):
    provider: str  # openai | internal
    internal_url: Optional[str] = None
    internal_model: Optional[str] = "llama3.1:8b"


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


@router.get("/llm-provider")
def get_llm_provider(db: Session = Depends(get_db)):
    """Get the current LLM provider settings."""
    settings = get_or_create_settings(db)
    
    return {
        "provider": settings.llm_provider or "openai",
        "internal_url": settings.internal_llm_url,
        "internal_model": settings.internal_llm_model or "llama3.1:8b",
        "openai_configured": bool(settings.openai_api_key)
    }


@router.put("/llm-provider")
def update_llm_provider(data: LLMProviderUpdate, db: Session = Depends(get_db)):
    """Update the LLM provider settings."""
    if data.provider not in ["openai", "internal"]:
        raise HTTPException(status_code=400, detail="Provider must be 'openai' or 'internal'")
    
    if data.provider == "internal" and not data.internal_url:
        raise HTTPException(status_code=400, detail="Internal URL is required when using internal provider")
    
    try:
        settings = get_or_create_settings(db)
        settings.llm_provider = data.provider
        
        if data.provider == "internal":
            settings.internal_llm_url = data.internal_url.strip() if data.internal_url else None
            settings.internal_llm_model = data.internal_model or "llama3.1:8b"
        
        db.commit()
        return {"message": f"LLM provider updated to {data.provider}"}
    except Exception as e:
        db.rollback()
        print(f"Error saving LLM provider settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save LLM provider settings: {str(e)}")


@router.post("/test-llm-connection")
def test_llm_connection(db: Session = Depends(get_db)):
    """Test the LLM connection based on current settings."""
    from backend.analysis.llm_client import get_llm_client, MockLLMClient, InternalLLMClient, OpenAILLMClient
    
    try:
        client = get_llm_client()
        
        # Check client type
        if isinstance(client, MockLLMClient):
            return {"success": False, "provider": "mock", "message": "No LLM configured - using mock client"}
        
        provider_name = "internal" if isinstance(client, InternalLLMClient) else "openai"
        
        # Simple test - try to make a minimal request
        if isinstance(client, InternalLLMClient):
            # For Ollama/vLLM, try listing models
            import httpx
            base_url = client.base_url.rstrip('/v1').rstrip('/')
            response = httpx.get(f"{base_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m.get('name', 'unknown') for m in models[:5]]
                return {
                    "success": True, 
                    "provider": provider_name,
                    "url": client.base_url,
                    "model": client.model,
                    "available_models": model_names,
                    "message": f"Connected! {len(models)} models available"
                }
            else:
                return {"success": False, "provider": provider_name, "message": f"Server responded with status {response.status_code}"}
        else:
            # For OpenAI, just return configured status
            return {"success": True, "provider": provider_name, "message": "OpenAI API key configured"}
            
    except Exception as e:
        return {"success": False, "provider": "unknown", "message": f"Connection failed: {str(e)}"}
