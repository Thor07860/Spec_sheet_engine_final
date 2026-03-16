# ==============================================================================
# services/extraction/extraction_helpers.py
# ==============================================================================
# PURPOSE
#   Utility functions for extraction service
#   Schema management, field detection, result merging
# ==============================================================================

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_model_for_document(model: str) -> str:
    """
    Normalize model names for document matching.
    Handles country suffixes and variations.

    Examples:
        SE100K-US → SE100K
        SE100K-US000 → SE100K
        SE7600H-US → SE7600H
        FRONIUS-10.0-3-S → FRONIUS-10.0-3-S
    """
    normalized = model.upper().strip()

    # Remove country suffixes
    normalized = re.sub(r"-US$", "", normalized)           # -US at end
    normalized = re.sub(r"-US[0-9]+$", "", normalized)     # -US000 at end
    normalized = re.sub(r"-[A-Z]{2}$", "", normalized)     # -DE, -FR, etc.

    # Remove regional variants (BNU, EU, etc.)
    normalized = re.sub(r"[A-Z]{2,3}\d*$", "", normalized).rstrip("-")

    return normalized


class ExtractionHelpers:
    """Utility functions for extraction service"""
    
    def ensure_schema_keys(self, extracted: dict, schema_template: dict) -> dict:
        """Ensure all schema keys exist in extracted data"""
        normalized = {}
        for key in schema_template.keys():
            normalized[key] = extracted.get(key)
        return normalized

    def get_missing_critical_fields(self, extracted: dict, schema_template: dict, critical_fields: set = None) -> list[str]:
        """Get list of critical missing fields"""
        missing = []
        fields_to_check = critical_fields if critical_fields else schema_template.keys()

        for field in fields_to_check:
            if field in schema_template and extracted.get(field) is None:
                missing.append(field)

        return missing

    def get_all_missing_fields(self, extracted: dict, schema_template: dict) -> list[str]:
        """Get list of all missing fields (excluding manufacturer, model)"""
        missing = []
        excluded_fields = {"manufacturer", "model"}

        for field in schema_template:
            if field in excluded_fields:
                continue
            if extracted.get(field) is None:
                missing.append(field)

        return missing

    def merge_results(self, base: dict, repair: dict, schema_template: dict) -> dict:
        """Merge repair results with base, only filling missing values"""
        merged = dict(base)

        for key in schema_template:
            if merged.get(key) is None and repair.get(key) is not None:
                merged[key] = repair[key]

        return merged

    def fill_nulls_with_defaults(self, extracted: dict, schema_template: dict) -> dict:
        """
        Replace ALL null/empty values with meaningful placeholders.
        Recursively handles nested dictionaries and lists.
        Ensures no actual null values in final output.
        """
        def fill_value(value):
            """Recursively fill null values"""
            if value is None:
                return "Not available"
            elif isinstance(value, dict):
                return {k: fill_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [fill_value(item) for item in value]
            elif isinstance(value, str):
                return str(value).strip() if str(value).strip() else "Not available"
            else:
                return value
        
        # Apply recursive fill to all extracted fields
        for key in extracted.keys():
            extracted[key] = fill_value(extracted[key])
        
        return extracted

    def build_alias_guide(self, schema_template: dict, field_aliases: dict) -> str:
        """Build human-readable alias guide for prompts"""
        alias_lines = []

        for field, aliases in field_aliases.items():
            if field in schema_template:
                alias_lines.append(f"{field} → {', '.join(aliases)}")

        return "\n".join(alias_lines)

    @staticmethod
    def preserve_units(value: any) -> dict:
        """
        Parse value and unit, preserving both.
        
        Examples:
            "5.76 kW" → {"value": 5.76, "unit": "kW", "original": "5.76 kW"}
            "49.6 V" → {"value": 49.6, "unit": "V", "original": "49.6 V"}
            "550" → {"value": 550, "unit": None, "original": "550"}
            "-0.27%/°C" → {"value": -0.27, "unit": "%/°C", "original": "-0.27%/°C"}
            "10000/500" → {"value": 10000, "unit": None, "original": "10000/500"} (takes first value)
            "0.775/1.7" → {"value": 0.775, "unit": None, "original": "0.775/1.7"} (takes first value)
        """
        if value is None or value == "":
            return {"value": None, "unit": None, "original": None}
        
        value_str = str(value).strip()
        if not value_str:
            return {"value": None, "unit": None, "original": None}

        # Handle dual-unit values like "10000/500" or "0.775/1.7"
        # Take the first value if multiple separated by /
        if "/" in value_str:
            parts = value_str.split("/")
            value_str = parts[0].strip()
            if not value_str:
                return {"value": None, "unit": None, "original": str(value)}

        # Pattern to match number followed by optional unit
        # Handles: 5.76, 5.76 kW, -0.27%/°C, 49.6V, etc.
        pattern = r'^([-+]?[\d.]+)\s*(.*)$'
        match = re.match(pattern, value_str)
        
        if match:
            numeric_part = match.group(1)
            unit_part = match.group(2).strip() if match.group(2) else None
            
            try:
                # Try to convert to number
                if '.' in numeric_part:
                    numeric_value = float(numeric_part)
                else:
                    numeric_value = int(numeric_part)
                
                return {
                    "value": numeric_value,
                    "unit": unit_part if unit_part else None,
                    "original": str(value)
                }
            except ValueError:
                return {"value": None, "unit": None, "original": str(value)}
        
        return {"value": None, "unit": None, "original": str(value)}

    @staticmethod
    def format_with_unit(numeric_value: any, unit: str = None) -> str:
        """
        Format numeric value with unit for storage/display.
        
        Examples:
            format_with_unit(5.76, "kW") → "5.76 kW"
            format_with_unit(49.6, "V") → "49.6 V"
            format_with_unit(550, None) → "550"
        """
        if numeric_value is None:
            return None
        
        value_str = str(numeric_value)
        if unit:
            return f"{value_str} {unit}".strip()
        return value_str

    @staticmethod
    def is_value_obviously_wrong(field_name: str, value: any) -> bool:
        """
        Quick sanity check: catches obviously truncated or incorrect values.
        
        Examples of bad values to catch:
            wattage_w = 9  (truncated from 10000 or 9000)
            wattage_w = 1  (truncated from 100+)
            isc_a = 0.7  (truncated from 7.0, 70, etc)
            voltage = 4  (truncated from 48, 400, etc)
        
        Returns True if value looks WRONG, False if it looks OK.
        """
        if value is None or value == "Not available":
            return False
        
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            return False
        
        # Define minimum realistic values for common fields
        MINIMUM_REALISTIC = {
            # Power/Wattage fields
            'wattage_w': 50,  # Single items < 50W are rare (micro-inverters min ~240W)
            'power_w': 50,
            'nominal_ac_power_output': 50,
            'peak_power_w': 100,
            'max_continuous_power_w': 100,
            'max_dc_input_w': 100,
            'max_ac_output_power_w': 100,
            
            # Voltage fields  
            'voc_v': 10,  # Open circuit voltage should be > 10V
            'vmp_v': 10,  # Max power voltage should be > 10V
            'nominal_voltage_v': 10,
            'max_input_voltage_v': 20,
            'max_dc_voltage_v': 20,
            'nominal_ac_voltage_v': 100,
            
            # Current fields
            'isc_a': 1,  # Short circuit current should be > 1A
            'imp_a': 1,  # Max power current should be > 1A
            'max_input_current_a': 1,
            'max_discharge_current_a': 1,
            'max_charge_current_a': 1,
            
            # Capacity fields
            'total_capacity_kwh': 0.5,
            'usable_capacity_kwh': 0.3,
            'nominal_capacity_kwh': 0.5,
            'energy_capacity': 0.5,
            
            # Frequency fields
            'frequency_hz': 40  # Should be ~50-60Hz
        }
        
        # Get minimum for this field (case-insensitive)
        field_lower = field_name.lower()
        min_val = None
        for key, threshold in MINIMUM_REALISTIC.items():
            if key.lower() == field_lower:
                min_val = threshold
                break
        
        # If we have a minimum and value is below it, it's probably wrong
        if min_val is not None and numeric_value < min_val:
            return True  # VALUE IS WRONG
        
        return False  # VALUE LOOKS OK
