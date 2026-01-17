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


class AppUrlUpdate(BaseModel):
    url: str


class LLMProviderUpdate(BaseModel):
    provider: str  # openai | internal | cambrian
    internal_url: Optional[str] = None
    internal_model: Optional[str] = "llama3.1:8b"
    cambrian_url: Optional[str] = "https://api.cambrian.pegatroncorp.com"
    cambrian_token: Optional[str] = None
    cambrian_model: Optional[str] = "LLAMA 3.3 70B"


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


@router.get("/app-url")
def get_app_url(db: Session = Depends(get_db)):
    """Get the application base URL."""
    settings = get_or_create_settings(db)
    return {"url": settings.app_base_url or "http://localhost:8000"}


@router.put("/app-url")
def update_app_url(data: AppUrlUpdate, db: Session = Depends(get_db)):
    """Update the application base URL."""
    if not data.url or not data.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
        
    try:
        settings = get_or_create_settings(db)
        # Remove trailing slash for consistency
        settings.app_base_url = data.url.strip().rstrip('/')
        db.commit()
        
        return {"message": "Application URL updated successfully", "url": settings.app_base_url}
    except Exception as e:
        db.rollback()
        print(f"Error saving App URL: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save App URL: {str(e)}")


@router.get("/llm-provider")
def get_llm_provider(db: Session = Depends(get_db)):
    """Get the current LLM provider settings."""
    settings = get_or_create_settings(db)
    
    provider = settings.llm_provider or "openai"
    internal_model = settings.internal_llm_model or "llama3.1:8b"
    cambrian_model = settings.cambrian_model or "LLAMA 3.3 70B"
    
    if provider == "cambrian":
        active_model = cambrian_model
        provider_display = "Cambrian"
    elif provider == "internal":
        active_model = internal_model
        provider_display = "Internal AI"
    else:
        active_model = "gpt-4o-mini"
        provider_display = "OpenAI"
    
    # Check if cambrian token is set
    cambrian_configured = False
    if settings.cambrian_token:
        try:
            encryption.decrypt(settings.cambrian_token)
            cambrian_configured = True
        except:
            pass
    
    return {
        "provider": provider,
        "provider_display": provider_display,
        "internal_url": settings.internal_llm_url,
        "internal_model": internal_model,
        "cambrian_url": settings.cambrian_url or "https://api.cambrian.pegatroncorp.com",
        "cambrian_model": cambrian_model,
        "cambrian_configured": cambrian_configured,
        "active_model": active_model,
        "openai_configured": bool(settings.openai_api_key)
    }


@router.put("/llm-provider")
def update_llm_provider(data: LLMProviderUpdate, db: Session = Depends(get_db)):
    """Update the LLM provider settings."""
    if data.provider not in ["openai", "internal", "cambrian"]:
        raise HTTPException(status_code=400, detail="Provider must be 'openai', 'internal', or 'cambrian'")
    
    if data.provider == "internal" and not data.internal_url:
        raise HTTPException(status_code=400, detail="Internal URL is required when using internal provider")
    
    if data.provider == "cambrian" and not data.cambrian_token:
        raise HTTPException(status_code=400, detail="Cambrian token is required when using Cambrian provider")
    
    try:
        settings = get_or_create_settings(db)
        settings.llm_provider = data.provider
        
        if data.provider == "internal":
            settings.internal_llm_url = data.internal_url.strip() if data.internal_url else None
            settings.internal_llm_model = data.internal_model or "llama3.1:8b"
        elif data.provider == "cambrian":
            settings.cambrian_url = data.cambrian_url.strip() if data.cambrian_url else "https://api.cambrian.pegatroncorp.com"
            settings.cambrian_token = encryption.encrypt(data.cambrian_token.strip()) if data.cambrian_token else None
            settings.cambrian_model = data.cambrian_model or "LLAMA 3.3 70B"
        
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


@router.get("/list-cambrian-models")
def list_cambrian_models(token: Optional[str] = None, url: Optional[str] = None, db: Session = Depends(get_db)):
    """Fetch available models from Cambrian LLM gateway."""
    import httpx
    
    settings = get_or_create_settings(db)
    base_url = url or settings.cambrian_url or "https://api.cambrian.pegatroncorp.com"
    
    # Use provided token or decrypt stored token
    api_token = token
    if not api_token and settings.cambrian_token:
        try:
            api_token = encryption.decrypt(settings.cambrian_token)
        except:
            pass
    
    if not api_token:
        return {"models": [], "error": "No Cambrian token configured"}
    
    # Normalize URL
    clean_url = base_url.rstrip('/')
    
    try:
        # Use Cambrian /assistant/llm_model endpoint
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json"
        }
        response = httpx.get(f"{clean_url}/assistant/llm_model", headers=headers, verify=False, timeout=10.0)
        
        if response.status_code == 200:
            data = response.json()
            models_list = data.get('llm_list', [])
            models = [m.get('name', 'unknown') for m in models_list if m.get('name')]
            return {"models": models, "source": "cambrian"}
        elif response.status_code == 401:
            return {"models": [], "error": "Authentication failed - invalid token"}
        else:
            return {"models": [], "error": f"Server returned status {response.status_code}"}
    except Exception as e:
        print(f"Cambrian API failed: {e}")
        return {"models": [], "error": f"Connection failed: {str(e)}"}


class TestConnectionRequest(BaseModel):
    url: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None  # Force test specific provider
    cambrian_token: Optional[str] = None


@router.post("/test-llm-connection")
def test_llm_connection(request: Optional[TestConnectionRequest] = None, db: Session = Depends(get_db)):
    """Test the LLM connection. Uses provided params if given, otherwise uses saved settings."""
    import httpx
    
    settings = get_or_create_settings(db)
    
    # Determine provider
    provider = (request.provider if request and request.provider else None) or settings.llm_provider or "openai"
    
    # If URL is provided in request without explicit provider, assume internal
    if request and request.url and not request.provider:
        provider = "internal"
    
    if provider == "cambrian":
        # Test Cambrian connection
        cambrian_url = settings.cambrian_url or "https://api.cambrian.pegatroncorp.com"
        cambrian_model = settings.cambrian_model or "LLAMA 3.3 70B"
        
        # Get token from request or settings
        api_token = request.cambrian_token if request and request.cambrian_token else None
        if not api_token and settings.cambrian_token:
            try:
                api_token = encryption.decrypt(settings.cambrian_token)
            except:
                pass
        
        if not api_token:
            return {"success": False, "provider": "cambrian", "message": "No Cambrian token configured"}
        
        clean_url = cambrian_url.rstrip('/')
        
        try:
            headers = {
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json"
            }
            response = httpx.get(f"{clean_url}/assistant/llm_model", headers=headers, verify=False, timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                models_list = data.get('llm_list', [])
                model_names = [m.get('name', 'unknown') for m in models_list[:5]]
                model_exists = any(m.get('name') == cambrian_model for m in models_list)
                
                return {
                    "success": True,
                    "provider": "cambrian",
                    "url": cambrian_url,
                    "model": cambrian_model,
                    "model_valid": model_exists,
                    "available_models": model_names,
                    "message": f"Connected! Model '{cambrian_model}' {'found' if model_exists else 'not found, please select from dropdown'}"
                }
            elif response.status_code == 401:
                return {"success": False, "provider": "cambrian", "message": "Authentication failed - invalid token"}
            else:
                return {"success": False, "provider": "cambrian", "message": f"Server responded with status {response.status_code}"}
        except Exception as e:
            return {"success": False, "provider": "cambrian", "message": f"Connection failed: {str(e)}"}
    
    elif provider == "internal":
        test_url = (request.url if request and request.url else None) or settings.internal_llm_url
        test_model = (request.model if request and request.model else None) or settings.internal_llm_model or "llama3.1:8b"
        
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


# ============================================================
# Module Owner Map Configuration (PRD Redmine Automation)
# ============================================================

import json
from pathlib import Path
from typing import Dict, Any

MODULE_OWNER_MAP_PATH = Path(__file__).parent.parent / "config" / "module_owner_map.json"


def get_default_module_owner_map() -> Dict[str, Any]:
    """Return default module owner map configuration."""
    return {
        "_description": "Module-Owner Mapping Configuration for Redmine Auto-Assignment",
        "module_patterns": {
            "CtsMedia*": {"team_name": "Multimedia Team", "redmine_user_id": None},
            "CtsCamera*": {"team_name": "Camera Team", "redmine_user_id": None},
            "CtsWifi*": {"team_name": "Connectivity Team", "redmine_user_id": None},
            "CtsNet*": {"team_name": "Connectivity Team", "redmine_user_id": None},
            "CtsBluetooth*": {"team_name": "Connectivity Team", "redmine_user_id": None},
        },
        "team_to_user_map": {
            "Multimedia Team": None,
            "Camera Team": None,
            "Connectivity Team": None,
            "Framework Team": None,
            "Default": None
        },
        "severity_to_priority": {
            "High": 5,
            "Medium": 4,
            "Low": 3
        },
        "default_settings": {
            "default_team": "Default",
            "default_priority_id": 4,
            "default_project_id": 1,
            "fallback_user_id": None
        }
    }


@router.get("/module-owner-map")
def get_module_owner_map():
    """Get the current module-owner mapping configuration."""
    try:
        if MODULE_OWNER_MAP_PATH.exists():
            with open(MODULE_OWNER_MAP_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return {"config": config, "path": str(MODULE_OWNER_MAP_PATH)}
        else:
            # Return default config
            return {"config": get_default_module_owner_map(), "path": str(MODULE_OWNER_MAP_PATH), "is_default": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {str(e)}")


class ModuleOwnerMapUpdate(BaseModel):
    config: Dict[str, Any]


@router.put("/module-owner-map")
def update_module_owner_map(data: ModuleOwnerMapUpdate):
    """Update the module-owner mapping configuration."""
    try:
        # Validate required top-level keys (team_to_user_map is now optional)
        required_keys = ["module_patterns", "default_settings"]
        for key in required_keys:
            if key not in data.config:
                raise HTTPException(status_code=400, detail=f"Missing required key: {key}")
        
        # Ensure config directory exists
        MODULE_OWNER_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Write config
        with open(MODULE_OWNER_MAP_PATH, 'w', encoding='utf-8') as f:
            json.dump(data.config, f, indent=2, ensure_ascii=False)
        
        # Reload the assignment resolver to pick up new config
        try:
            from backend.integrations.assignment_resolver import AssignmentResolver
            AssignmentResolver._instance = None
            AssignmentResolver._config = None
        except:
            pass
        
        return {"message": "Module owner map updated successfully", "path": str(MODULE_OWNER_MAP_PATH)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")


@router.post("/module-owner-map/reset")
def reset_module_owner_map():
    """Reset module-owner mapping to default configuration."""
    try:
        default_config = get_default_module_owner_map()
        
        MODULE_OWNER_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(MODULE_OWNER_MAP_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        # Reload the assignment resolver
        try:
            from backend.integrations.assignment_resolver import AssignmentResolver
            AssignmentResolver._instance = None
            AssignmentResolver._config = None
        except:
            pass
        
        return {"message": "Module owner map reset to defaults", "config": default_config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset config: {str(e)}")


@router.get("/all")
def get_all_settings(db: Session = Depends(get_db)):
    """Get all settings for frontend initialization."""
    settings = get_or_create_settings(db)
    
    # Get module owner map
    module_map = {}
    try:
        if MODULE_OWNER_MAP_PATH.exists():
            with open(MODULE_OWNER_MAP_PATH, 'r', encoding='utf-8') as f:
                module_map = json.load(f)
    except:
        module_map = get_default_module_owner_map()
    
    return {
        "redmine": {
            "url": settings.redmine_url,
            "is_configured": bool(settings.redmine_url and settings.redmine_api_key)
        },
        "app_url": settings.app_base_url or "http://localhost:8000",
        "llm_provider": settings.llm_provider or "openai",
        "module_owner_map": module_map,
        "default_project_id": module_map.get("default_settings", {}).get("default_project_id", 1)
    }

