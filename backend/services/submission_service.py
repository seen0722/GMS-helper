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
        build_product: str = None,
        build_brand: str = None,
        build_model: str = None,
        build_device: str = None,
        security_patch: str = None
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
        is_system_replace = (
            (suite_name == "CTS" and suite_plan and "cts-on-gsi" in suite_plan.lower()) or
            (suite_name == "VTS" and suite_plan and "vts" in suite_plan.lower())
        )

        match_suffix = "" # For naming if needed
        if not submission and is_system_replace:
            fp_pattern = re.compile(r"^([^:]+):([^/]+)/([^/]+)(/.+)$")
            match = fp_pattern.match(fingerprint)
            if match:
                prefix = match.group(1)
                suffix = match.group(4)
                match_suffix = suffix
                
                candidates = db.query(models.Submission).filter(
                     models.Submission.target_fingerprint.like(f"{prefix}:%")
                ).order_by(desc(models.Submission.updated_at)).limit(20).all()
                
                for cand in candidates:
                    if not cand.target_fingerprint: continue
                    c_match = fp_pattern.match(cand.target_fingerprint)
                    if c_match:
                        c_prefix = c_match.group(1)
                        c_suffix = c_match.group(4)
                        if c_prefix == prefix and c_suffix == suffix:
                            submission = cand
                            print(f"Grouped System-Replace Run ({suite_name}) to Submission {submission.id}")
                            break

        if not submission:
            # Create new submission with 3PL Naming Convention
            # Formula: [Brand] [Model] ([Device]) - [Security Patch] (Build: [Suffix_Partial])
            brand = build_brand or "Unknown"
            model = build_model or build_product or "Device"
            device = build_device or "Unknown"
            patch = security_patch or "NoPatch"
            
            # Simple suffix indicator from Build ID or Fingerprint
            suffix_label = "Unknown"
            fp_pattern = re.compile(r"^([^:]+):([^/]+)/([^/]+)(/.+)$")
            m = fp_pattern.match(fingerprint)
            if m:
                # Extract starting vendor version from suffix like /02.00.11... -> 02.00.11
                raw_suffix = m.group(4).lstrip('/')
                suffix_label = raw_suffix.split('_')[0].split(':')[0]
            
            sub_name = f"{brand} {model} ({device}) - {patch} (Build: {suffix_label})"
            
            submission = models.Submission(
                name=sub_name,
                target_fingerprint=fingerprint,
                status="analyzing",
                gms_version=android_version,
                product=build_product,
                brand=brand,
                device=device
            )
            db.add(submission)
            db.flush()
            print(f"Created new Submission ID: {submission.id} for fingerprint: {fingerprint}")
        else:
            print(f"Matched Submission ID: {submission.id} for fingerprint: {fingerprint}")
            
        return submission
