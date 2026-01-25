from backend.database.database import SessionLocal, engine
from backend.database import models

db = SessionLocal()

# Initial configs
configs = [
    models.TestSuiteConfig(name="CTS", display_name="CTS", is_required=1, match_rule="Standard", sort_order=1),
    models.TestSuiteConfig(name="CTSonGSI", display_name="CTS on GSI", is_required=1, match_rule="GSI", sort_order=2),
    models.TestSuiteConfig(name="VTS", display_name="VTS", is_required=1, match_rule="Standard", sort_order=3),
    models.TestSuiteConfig(name="GTS", display_name="GTS", is_required=1, match_rule="Standard", sort_order=4),
    models.TestSuiteConfig(name="STS", display_name="STS", is_required=1, match_rule="Standard", sort_order=5),
]

for c in configs:
    exists = db.query(models.TestSuiteConfig).filter_by(name=c.name).first()
    if not exists:
        print(f"Adding {c.name}")
        db.add(c)
    else:
        print(f"Skipping {c.name} (exists)")

db.commit()
print("Seeding complete.")
db.close()
