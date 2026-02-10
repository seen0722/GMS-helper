from sqlalchemy.orm import Session
from backend.database.database import SessionLocal
from backend.database import models

def get_standard_suites():
    """Return the list of standard GMS test suites."""
    return [
        {
            "name": "CTS",
            "display_name": "CTS",
            "is_required": 1,
            "match_rule": "Standard",
            "sort_order": 1,
            "description": "Compatibility Test Suite"
        },
        {
            "name": "VTS",
            "display_name": "VTS",
            "is_required": 1,
            "match_rule": "Standard",
            "sort_order": 2,
            "description": "Vendor Test Suite"
        },
        {
            "name": "GTS",
            "display_name": "GTS",
            "is_required": 1,
            "match_rule": "Standard",
            "sort_order": 3,
            "description": "GMS Test Suite"
        },
        {
            "name": "STS",
            "display_name": "STS",
            "is_required": 1,
            "match_rule": "Standard",
            "sort_order": 4,
            "description": "Security Test Suite"
        },
        {
            "name": "CTS-on-GSI",
            "display_name": "CTS on GSI",
            "is_required": 1,
            "match_rule": "GSI",
            "sort_order": 5,
            "description": "CTS on Generic System Image"
        }
    ]

def bootstrap_database():
    """Ensure standard configurations exist in the database."""
    db = SessionLocal()
    try:
        suites = get_standard_suites()
        
        # We check each suite by name to avoid duplicates but ensure they exist
        for s in suites:
            existing = db.query(models.TestSuiteConfig).filter(models.TestSuiteConfig.name == s["name"]).first()
            if not existing:
                print(f"[Bootstrap] Adding missing suite: {s['name']}")
                new_suite = models.TestSuiteConfig(**s)
                db.add(new_suite)
            else:
                # Optionally sync configuration if needed
                # existing.display_name = s["display_name"]
                pass
        
        db.commit()
    except Exception as e:
        print(f"[Bootstrap] Error during initialization: {e}")
        db.rollback()
    finally:
        db.close()
