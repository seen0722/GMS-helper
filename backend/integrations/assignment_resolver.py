"""
Assignment Resolver Module

This module provides logic to resolve Redmine assignment based on:
1. Module Name -> Redmine User ID (glob pattern matching)
2. Severity -> Priority ID

Simplified version without team intermediate layer.

Author: Chen Zeming
Date: 2026-01-17
"""

import json
import fnmatch
from pathlib import Path
from typing import Optional, Dict, Any


class AssignmentResolver:
    """
    Resolves Redmine assignment details based on module names and AI analysis.
    
    Uses a JSON configuration file for flexible mapping without code changes.
    """
    
    _instance = None
    _config = None
    
    def __new__(cls):
        """Singleton pattern to avoid reloading config on every call."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self):
        """Load configuration from JSON file."""
        config_path = Path(__file__).parent.parent / "config" / "module_owner_map.json"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Config file not found at {config_path}. Using defaults.")
            self._config = self._get_default_config()
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in config file: {e}. Using defaults.")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if file is missing."""
        return {
            "module_patterns": {},
            "default_settings": {
                "default_priority_id": 4,
                "fallback_user_id": None,
                "default_project_id": 1
            }
        }
    
    def reload_config(self):
        """Force reload of configuration file."""
        self._config = None
        self._load_config()
    
    def get_user_id_for_module(self, module_name: str) -> tuple[Optional[int], str]:
        """
        Get Redmine User ID directly from module name using glob pattern matching.
        
        Args:
            module_name: CTS/VTS module name (e.g., "CtsMediaTestCases")
            
        Returns:
            Tuple of (Redmine User ID, source). 
            source is 'module_pattern' if matched, 'fallback' if used default.
        """
        if not module_name:
            return self._get_fallback_user_id(), "fallback"
        
        module_patterns = self._config.get("module_patterns", {})
        
        for pattern, info in module_patterns.items():
            if fnmatch.fnmatch(module_name, pattern):
                user_id = info.get("redmine_user_id")
                if user_id is not None:
                    return user_id, "module_pattern"
        
        return self._get_fallback_user_id(), "fallback"
    
    def _get_fallback_user_id(self) -> Optional[int]:
        """Get the fallback user ID from default settings."""
        return self._config.get("default_settings", {}).get("fallback_user_id")
    
    def get_default_project_id(self) -> int:
        """Get default project ID from config."""
        return self._config.get("default_settings", {}).get("default_project_id", 1)
    
    def get_priority_for_severity(self, severity: str) -> int:
        """
        Convert AI severity to Redmine Priority ID.
        
        Args:
            severity: One of "High", "Medium", "Low"
            
        Returns:
            Redmine Priority ID (default: 4 for Medium)
        """
        severity_map = self._config.get("severity_to_priority", {
            "High": 5,
            "Medium": 4,
            "Low": 3
        })
        default_priority = self._config.get("default_settings", {}).get("default_priority_id", 4)
        
        return severity_map.get(severity, default_priority)
    
    def resolve_assignment(
        self, 
        module_name: str, 
        severity: str = "Medium"
    ) -> Dict[str, Any]:
        """
        Full resolution: Get all assignment details for a cluster/module.
        
        Args:
            module_name: CTS/VTS module name
            severity: AI's severity assessment
            
        Returns:
            Dict with keys: user_id, priority_id, project_id, resolved_from
        """
        user_id, source = self.get_user_id_for_module(module_name)
        priority_id = self.get_priority_for_severity(severity)
        project_id = self.get_default_project_id()
        
        return {
            "user_id": user_id,
            "priority_id": priority_id,
            "project_id": project_id,
            "resolved_from": source
        }


# Convenience function for quick access
def get_assignment_resolver() -> AssignmentResolver:
    """Get the singleton AssignmentResolver instance."""
    return AssignmentResolver()

