import re
from backend.database.database import SessionLocal
from backend.database import models

def rename_submissions():
    db = SessionLocal()
    submissions = db.query(models.Submission).all()
    
    fp_pattern = re.compile(r"^([^:]+):([^/]+)/([^/]+)(/.+)$")
    
    renamed_count = 0
    for sub in submissions:
        if not sub.target_fingerprint: continue
        
        # Check if currently contains "(Unknown)" or follows old pattern
        if "(Unknown)" in sub.name or " · " in sub.name:
            m = fp_pattern.match(sub.target_fingerprint)
            if m:
                # Re-parse metadata
                prefix_parts = m.group(1).split('/')
                brand = ""
                model = "Device"
                device = "Unknown"
                
                if len(prefix_parts) >= 3:
                    brand = prefix_parts[0]
                    model = prefix_parts[1]
                    device = prefix_parts[2]
                elif len(prefix_parts) == 1:
                    device = prefix_parts[0]
                
                # Suffix
                raw_suffix = m.group(4).lstrip('/')
                suffix = raw_suffix.split('_')[0].split(':')[0]
                
                new_name = f"{brand} {model} ({device}) · {suffix}".strip()
                
                if sub.name != new_name:
                    print(f"Renaming Submission #{sub.id}: '{sub.name}' -> '{new_name}'")
                    sub.name = new_name
                    sub.brand = brand
                    sub.device = device
                    renamed_count += 1
    
    db.commit()
    print(f"Renamed {renamed_count} submissions.")
    db.close()

if __name__ == "__main__":
    rename_submissions()
