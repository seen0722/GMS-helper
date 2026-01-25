
from enum import Enum
from typing import List, Dict

class FailureCategory(str, Enum):
    # Core BSP
    MULTIMEDIA = "Multimedia (Audio/Video/DRM)"
    CONNECTIVITY = "Connectivity (WiFi/BT/NFC/GPS)"
    GRAPHICS_DISPLAY = "Graphics & Display"
    SENSORS = "Sensors & Input"
    POWER_THERMAL = "Power & Thermal"
    STORAGE = "Storage & Memory"
    SECURITY = "Security & Permissions"
    
    # System
    SYSTEM_FRAMEWORK = "Android System Framework"
    VENDOR_HAL = "Vendor HAL / Driver"
    KERNEL = "Kernel / Stability"
    
    # Infra
    TEST_INFRASTRUCTURE = "Test Infrastructure / Harness"
    UI_AUTOMATION = "UI Automation"
    
    # Other
    UNKNOWN = "Unknown / Uncategorized"

# Mapping components/modules to Categories (Heuristic Fallback)
MODULE_CATEGORY_MAP = {
    "CtsMedia": FailureCategory.MULTIMEDIA,
    "CtsMultimedia": FailureCategory.MULTIMEDIA,
    "CtsCamera": FailureCategory.MULTIMEDIA,
    "CtsAudio": FailureCategory.MULTIMEDIA,
    "CtsDrm": FailureCategory.MULTIMEDIA,
    "CtsBluetooth": FailureCategory.CONNECTIVITY,
    "CtsWifi": FailureCategory.CONNECTIVITY,
    "CtsNfc": FailureCategory.CONNECTIVITY,
    "CtsNet": FailureCategory.CONNECTIVITY,
    "CtsLocation": FailureCategory.CONNECTIVITY,
    "CtsGraphics": FailureCategory.GRAPHICS_DISPLAY,
    "CtsDisplay": FailureCategory.GRAPHICS_DISPLAY,
    "CtsSensor": FailureCategory.SENSORS,
    "CtsSecurity": FailureCategory.SECURITY,
    "CtsPermission": FailureCategory.SECURITY,
    "CtsFileSystem": FailureCategory.STORAGE,
    "CtsApp": FailureCategory.SYSTEM_FRAMEWORK,
    "CtsOs": FailureCategory.SYSTEM_FRAMEWORK,
    "CtsView": FailureCategory.UI_AUTOMATION,
    "CtsWidget": FailureCategory.UI_AUTOMATION,
}

def get_category_for_module(module_name: str) -> str:
    """Heuristic to guess category from module name."""
    for key, cat in MODULE_CATEGORY_MAP.items():
        if key in module_name:
            return cat.value
    return FailureCategory.UNKNOWN.value

# Severity Definitions
class Severity(str, Enum):
    CRITICAL = "Critical" # System Crash, Hang, Security Vuln
    HIGH = "High"         # Functional Blocker, Persistent failure in major feature
    MEDIUM = "Medium"     # Standard functional failure
    LOW = "Low"           # Flake, Minor UI, Logging
