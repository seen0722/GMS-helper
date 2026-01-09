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
    
    provider = settings.llm_provider or "openai"
    internal_model = settings.internal_llm_model or "llama3.1:8b"
    
    active_model = internal_model if provider == "internal" else "gpt-4o-mini"
    provider_display = "Internal AI" if provider == "internal" else "OpenAI"
    
    return {
        "provider": provider,
        "provider_display": provider_display,
        "internal_url": settings.internal_llm_url,
        "internal_model": internal_model,
        "active_model": active_model,
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


@router.get("/list-models")
def list_available_models(url: Optional[str] = None, db: Session = Depends(get_db)):
    """Fetch available models from the internal LLM server (Ollama/vLLM).
    
    Args:
        url: Optional URL to query. If not provided, uses the saved internal_llm_url.
    """
    import httpx
    
    settings = get_or_create_settings(db)
    base_url = url or settings.internal_llm_url
    
    if not base_url:
        return {"models": [], "error": "No internal LLM URL configured"}
    
    # Normalize URL - remove trailing /v1 if present for Ollama API
    clean_url = base_url.rstrip('/').rstrip('/v1').rstrip('/')
    
    models = []
    
    try:
        # Try Ollama format first: GET /api/tags
        response = httpx.get(f"{clean_url}/api/tags", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            ollama_models = data.get('models', [])
            models = [m.get('name', 'unknown') for m in ollama_models]
            return {"models": models, "source": "ollama"}
    except Exception as e:
        print(f"Ollama API failed: {e}")
    
    try:
        # Try OpenAI-compatible format: GET /v1/models
        response = httpx.get(f"{clean_url}/v1/models", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            openai_models = data.get('data', [])
            models = [m.get('id', 'unknown') for m in openai_models]
            return {"models": models, "source": "openai-compatible"}
    except Exception as e:
        print(f"OpenAI-compatible API failed: {e}")
    
    return {"models": [], "error": "Failed to fetch models from server"}


class TestConnectionRequest(BaseModel):
    url: Optional[str] = None
    model: Optional[str] = None


@router.post("/test-llm-connection")
def test_llm_connection(request: Optional[TestConnectionRequest] = None, db: Session = Depends(get_db)):
    """Test the LLM connection. Uses provided URL/model if given, otherwise uses saved settings."""
    import httpx
    
    settings = get_or_create_settings(db)
    
    # Use request params if provided, otherwise fall back to saved settings
    test_url = (request.url if request and request.url else None) or settings.internal_llm_url
    test_model = (request.model if request and request.model else None) or settings.internal_llm_model or "llama3.1:8b"
    provider = settings.llm_provider or "openai"
    
    # If URL is provided in request, assume testing internal provider
    if request and request.url:
        provider = "internal"
    
    if provider == "internal":
        if not test_url:
            return {"success": False, "provider": "internal", "message": "No internal LLM URL configured"}
        
        # Normalize URL
        clean_url = test_url.rstrip('/').rstrip('/v1').rstrip('/')
        
        try:
            # Test Ollama connection
            response = httpx.get(f"{clean_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m.get('name', 'unknown') for m in models[:5]]
                
                # Check if selected model exists
                model_exists = any(m.get('name') == test_model for m in models)
                
                return {
                    "success": True, 
                    "provider": "internal",
                    "url": test_url,
                    "model": test_model,
                    "model_valid": model_exists,
                    "available_models": model_names,
                    "message": f"Connected! Model '{test_model}' {'found' if model_exists else 'not found, please select from dropdown'}"
                }
            else:
                return {"success": False, "provider": "internal", "message": f"Server responded with status {response.status_code}"}
        except Exception as e:
            return {"success": False, "provider": "internal", "message": f"Connection failed: {str(e)}"}
    else:
        # OpenAI provider
        if settings.openai_api_key:
            return {"success": True, "provider": "openai", "message": "OpenAI API key configured"}
        else:
            return {"success": False, "provider": "openai", "message": "No OpenAI API key configured"}

