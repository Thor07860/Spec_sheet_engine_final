# ==============================================================================
# services/extraction/extraction_parsing.py
# ==============================================================================
# PURPOSE
#   JSON parsing and payload normalization for extraction results
# ==============================================================================

import json
import logging
import re
from typing import Optional, Any
from .extraction_helpers import ExtractionHelpers

logger = logging.getLogger(__name__)


class ExtractionParser:
    """Handles parsing and normalization of Gemini responses"""

    def parse_response(self, raw_text: Any) -> Optional[Any]:
        """
        Parse Gemini response into JSON.
        Handles various formats (direct JSON, markdown code blocks, embedded JSON)
        """
        if raw_text is None:
            return None

        if isinstance(raw_text, (dict, list)):
            return raw_text

        if not isinstance(raw_text, str):
            raw_text = str(raw_text)

        if not raw_text:
            return None

        # Try direct JSON parse
        try:
            return json.loads(raw_text)
        except Exception:
            pass

        # Try removing markdown code blocks
        cleaned = re.sub(r"```(?:json)?", "", raw_text).replace("```", "").strip()

        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # Try finding JSON object in text
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass

        logger.error("Gemini JSON parse failed. Raw preview: %r", raw_text[:500])
        return None

    def normalize_extracted_payload(
        self,
        parsed: Any,
        schema_template: dict
    ) -> Optional[dict]:
        """
        Normalize parsed payload into dict format.
        Handles list responses by extracting first dict item.
        """
        if isinstance(parsed, dict):
            return parsed

        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    return item

        return None

    def apply_internet_confidence(self, extracted: dict) -> dict:
        """
        Apply metadata showing values came from grounded web search.
        
        We do not overwrite existing real fields because _merge_results only fills
        missing values.
        """
        if not extracted:
            return extracted

        extracted["_source"] = "grounded_web_search"
        extracted["_confidence_modifier"] = 0.65
        return extracted

    def preserve_units_in_extraction(self, extracted: dict) -> dict:
        """
        Process extraction results to preserve units throughout.
        
        Processes all numeric fields to maintain units:
            "5.76 kW" → kept as "5.76 kW"
            "49.6 V" → kept as "49.6 V"
            "550" → kept as "550"
        
        Prevents unit stripping during normalization.
        """
        if not extracted:
            return extracted
        
        # Fields that should preserve units
        unit_preserving_fields = {
            'wattage_w', 'power_w', 'nominal_ac_power_output',
            'voc_v', 'vmp_v', 'isc_a', 'imp_a', 'input_voltage', 'output_voltage',
            'frequency_hz', 'max_input_voltage', 'temperature_coefficient_pmax',
            'nominal_capacity_kwh', 'usable_capacity_kwh', 'energy_capacity',
            'nominal_power', 'ac_rating', 'dc_rating'
        }
        
        processed = {}
        for field, value in extracted.items():
            if field in unit_preserving_fields and value is not None:
                # Parse to extract value and unit
                parsed = ExtractionHelpers.preserve_units(value)
                if parsed['value'] is not None and parsed['unit'] is not None:
                    # Preserve the unit
                    processed[field] = ExtractionHelpers.format_with_unit(
                        parsed['value'], 
                        parsed['unit']
                    )
                else:
                    # No unit found, keep original
                    processed[field] = value
            else:
                processed[field] = value
        
        return processed
