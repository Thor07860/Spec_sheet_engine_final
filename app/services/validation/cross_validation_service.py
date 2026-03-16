# ==============================================================================
# app/services/validation/cross_validation_service.py
# ==============================================================================
# PASS 4: Cross-validates extracted values against trusted manufacturer sources
# ==============================================================================

import logging
from typing import Dict, Tuple
from app.services.validation.trusted_domains import is_trusted_source, categorize_source
from app.services.validation.range_validator import RangeValidator

logger = logging.getLogger(__name__)


class CrossValidationService:
    """
    PASS 4 Service: Validates extracted specs against trusted sources
    Ensures values are realistic and from official manufacturer domains
    """

    @staticmethod
    def validate_extraction(
        extracted_data: dict,
        equipment_sub_type: str,
        manufacturer: str,
        source_url: str
    ) -> Tuple[dict, dict, float]:
        """
        Cross-validate extraction against trusted sources
        
        Args:
            extracted_data: Data extracted from PDF/web
            equipment_sub_type: Type of equipment (pv_module, string_inverter, etc)
            manufacturer: Equipment manufacturer
            source_url: Source where data was extracted from
        
        Returns:
            (validated_data, validation_results, confidence_adjustment)
        """
        
        logger.info("PASS 4: Cross-Validating extraction against trusted sources...")
        
        validated_data = extracted_data.copy()
        validation_results = {
            "source_trusted": False,
            "source_category": "untrusted",
            "range_validation_passed": False,
            "range_validation_message": "",
            "fields_rejected": []
        }
        
        confidence_adjustment = 0.0
        
        # ====================================================================
        # CHECK 1: Is source from trusted manufacturer domain?
        # ====================================================================
        source_trusted = is_trusted_source(source_url or "", manufacturer)
        source_category = categorize_source(source_url or "", manufacturer)
        
        validation_results["source_trusted"] = source_trusted
        validation_results["source_category"] = source_category
        
        if source_trusted:
            logger.info("✅ PASS 4: Source is TRUSTED (manufacturer domain)")
            confidence_adjustment += 0.15
        elif source_category == "blocked":
            logger.warning("❌ PASS 4: Source is BLOCKED (untrusted domain)")
            confidence_adjustment -= 0.25
        else:
            logger.warning("⚠️  PASS 4: Source is UNTRUSTED (third-party)")
            confidence_adjustment -= 0.10
        
        # ====================================================================
        # CHECK 2: Do values fall within realistic ranges?
        # ====================================================================
        is_valid, validation_msg = RangeValidator.validate_by_subtype(
            equipment_sub_type,
            extracted_data
        )
        
        validation_results["range_validation_passed"] = is_valid
        validation_results["range_validation_message"] = validation_msg
        
        if is_valid:
            logger.info("✅ PASS 4: Range validation PASSED - specs are realistic")
            confidence_adjustment += 0.15
        else:
            logger.warning(f"❌ PASS 4: Range validation FAILED - {validation_msg}")
            confidence_adjustment -= 0.20
            # Still use data but flag it
            validated_data["_range_validation_failed"] = validation_msg
        
        # ====================================================================
        # FINAL CONFIDENCE CALCULATION
        # ====================================================================
        # Base confidence from extraction (if provided in input)
        base_confidence = extracted_data.get("_extraction_confidence", 0.70)
        
        # Apply adjustments
        final_confidence = base_confidence + confidence_adjustment
        final_confidence = max(0.20, min(1.0, final_confidence))  # Clamp 0.20-1.0
        
        logger.info(
            "✅ PASS 4 Complete | Source: %s | Validation: %s | "
            "Base Conf: %.2f → Final Conf: %.2f",
            source_category,
            "PASS" if is_valid else "FAIL",
            base_confidence,
            final_confidence
        )
        
        validated_data["_pass4_confidence"] = final_confidence
        validated_data["_validation_results"] = validation_results
        
        return validated_data, validation_results, final_confidence

    @staticmethod
    def get_confidence_breakdown(confidence_data: dict) -> str:
        """Generate human-readable confidence explanation"""
        source_cat = confidence_data.get("source_category", "unknown")
        range_pass = confidence_data.get("range_validation_passed", False)
        
        explanation = f"Confidence Breakdown:\n"
        explanation += f"  Source: {source_cat}\n"
        explanation += f"  Range Validation: {'PASS' if range_pass else 'FAIL'}\n"
        
        if confidence_data.get("fields_rejected"):
            explanation += f"  Rejected Fields: {', '.join(confidence_data['fields_rejected'])}\n"
        
        return explanation
