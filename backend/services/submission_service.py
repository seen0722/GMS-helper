import re
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.database import models

class SubmissionService:
    @staticmethod
    def get_or_create_submission(
        db: Session,
        fingerprint: str,
        suite_name: str,
        suite_plan: str,
        android_version: str = None,
        build_product: str = None
    ) -> models.Submission:
        """
        Identify existing submission for grouping or create a new one.
        Handles:
        1. Exact Fingerprint Match
        2. System-Replace Match (GSI/VTS): Hardware Prefix + Vendor Suffix Match
        """
        if not fingerprint or fingerprint == "Pending..." or fingerprint == "Unknown":
            return None

        # 1. Try Exact Fingerprint Match
        submission = db.query(models.Submission).filter(
            models.Submission.target_fingerprint == fingerprint
        ).order_by(desc(models.Submission.updated_at)).first()
        
        # 2. GSI / VTS Fingerprint Match (Hardware Prefix + Vendor Suffix Match)
        # Requirement: 
        # - suite_name="CTS" AND suite_plan contains "cts-on-gsi"
        # - OR suite_name="VTS" AND suite_plan contains "vts"
        is_system_replace = (
            (suite_name == "CTS" and suite_plan and "cts-on-gsi" in suite_plan.lower()) or
            (suite_name == "VTS" and suite_plan and "vts" in suite_plan.lower())
        )

        if not submission and is_system_replace:
            # Regex: Group 1 (Prefix), Group 2 (Version), Group 3 (Build ID), Group 4 (Suffix)
            # Pattern: ^([^:]+):([^/]+)/([^/]+)(/.+)$
            # Example: Trimble/T70/thorpe:11/RKQ1.240423.001/02.00.11...
            fp_pattern = re.compile(r"^([^:]+):([^/]+)/([^/]+)(/.+)$")
            
            match = fp_pattern.match(fingerprint)
            if match:
                prefix = match.group(1) # e.g. Trimble/T70/thorpe
                suffix = match.group(4) # e.g. /02.00.11...
                
                # Find candidates with same Prefix (Brand/Product/Device)
                candidates = db.query(models.Submission).filter(
                     models.Submission.target_fingerprint.like(f"{prefix}:%")
                ).order_by(desc(models.Submission.updated_at)).limit(20).all()
                
                for cand in candidates:
                    if not cand.target_fingerprint: continue
                    c_match = fp_pattern.match(cand.target_fingerprint)
                    if c_match:
                        c_prefix = c_match.group(1)
                        c_suffix = c_match.group(4)
                        
                        # Match hardware/vendor parts precisely
                        if c_prefix == prefix and c_suffix == suffix:
                            submission = cand
                            print(f"Grouped System-Replace Run ({suite_name}) to Submission {submission.id}")
                            break

        if not submission:
            # Create new submission
            prod = build_product or "Unknown Device"
            sub_name = f"Submission {prod} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
            
            submission = models.Submission(
                name=sub_name,
                target_fingerprint=fingerprint,
                status="analyzing",
                gms_version=android_version,
                product=build_product
            )
            db.add(submission)
            db.flush() # Generate ID
            print(f"Created new Submission ID: {submission.id} for fingerprint: {fingerprint}")
        else:
            print(f"Matched Submission ID: {submission.id} for fingerprint: {fingerprint}")
            
        return submission
