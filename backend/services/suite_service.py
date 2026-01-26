from typing import Optional
from backend.database import models

class SuiteService:
    @staticmethod
    def match_suite(run: models.TestRun, config: models.TestSuiteConfig, target_fingerprint: Optional[str] = None) -> bool:
        """
        Determines if a TestRun belongs to a specific TestSuiteConfig (e.g., CTS, CTS-on-GSI).
        
        Args:
            run: The TestRun object.
            config: The TestSuiteConfig object definition rules.
            target_fingerprint: The target fingerprint of the Submission (used for standard CTS logic).
        """
        name = (run.test_suite_name or '').upper()
        plan = (run.suite_plan or '').lower()
        
        # GSI Logic
        if config.match_rule == 'GSI':
            # It matches if:
            # 1. suite_plan is 'cts-on-gsi' (Strongest Signal)
            # 2. OR explicit GSI product (relying on ABSOLUTE signals only)
            is_gsi_plan = 'cts-on-gsi' in plan
            is_gsi_product = (run.build_product and 'gsi' in run.build_product.lower()) or \
                             (run.build_model and 'gsi' in run.build_model.lower())
                             
            # Must be a CTS suite AND have GSI indicators
            return ('CTS' in name and (is_gsi_plan or is_gsi_product))
            
        # Standard CTS Logic (Default)
        if config.name == 'CTS':
            # Matches CTS only if NOT GSI
            is_gsi_plan = 'cts-on-gsi' in plan
            is_gsi_product = (run.build_product and 'gsi' in run.build_product.lower()) or \
                             (run.build_model and 'gsi' in run.build_model.lower())
            
            is_gsi = is_gsi_plan or is_gsi_product
            
            # Standard CTS = Name has CTS AND Not GSI
            # Note: We previously checked fingerprint mismatch, but that's unreliable if Target itself is GSI.
            # So we stick to explicit GSI checks only.
            return 'CTS' in name and not is_gsi
            
        # Generic String Match (e.g. VTS, GTS, STS)
        return config.name in name
