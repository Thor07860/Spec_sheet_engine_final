# ==============================================================================
# services/validation/validation_service.py (REFACTORED)
# ==============================================================================
# PURPOSE
#   Field-level validation for extracted equipment specification data.
#   Cross-field validation has been moved to validation/cross_field_validator.py
#
# FEATURES
#   • Schema-driven validation with type detection
#   • Settings-based thresholds (VALIDATION_PASS_THRESHOLD, VALIDATION_PARTIAL_THRESHOLD)
#   • Power/voltage/current/efficiency validators
#   • Confidence scoring
#   • Field coverage tracking
# ==============================================================================

from typing import Optional, Any
import logging
import re

from app.core.config import settings
from .cross_field_validator import CrossFieldValidator

logger = logging.getLogger(__name__)


# Fields always filled from request — do not count toward Gemini coverage
EXCLUDED_FROM_COUNT = {"manufacturer", "model"}

# Internal system metadata fields — do not validate as schema values
INTERNAL_METADATA_FIELDS = {"_source", "_confidence_modifier"}


class ValidationResult:
    """Encapsulates validation result with scores and errors"""
    
    def __init__(
        self,
        is_valid: bool,
        status: str,
        cleaned_data: Optional[dict],
        errors: list,
        confidence_score: float,
        fields_extracted: int,
        fields_expected: int
    ):
        self.is_valid = is_valid
        self.status = status
        self.cleaned_data = cleaned_data
        self.errors = errors
        self.confidence_score = confidence_score
        self.fields_extracted = fields_extracted
        self.fields_expected = fields_expected


class ValidationService:
    """Field-level validation of extraction results"""
    
    def __init__(self):
        self.cross_field_validator = CrossFieldValidator()
    
    def validate(
        self,
        raw_data: dict,
        schema_template: dict,
        equipment_sub_type: str
    ) -> ValidationResult:
        """
        Validate extracted data against schema template.
        
        Returns:
            ValidationResult with is_valid, status, cleaned_data, errors, confidence, field counts
        """
        errors = []
        cleaned_data = {}

        if not isinstance(raw_data, dict):
            return ValidationResult(
                is_valid=False,
                status="failed",
                cleaned_data=None,
                errors=[f"Invalid data type: expected dict, got {type(raw_data).__name__}"],
                confidence_score=0.0,
                fields_extracted=0,
                fields_expected=len(schema_template)
            )

        countable_fields = [
            f for f in schema_template.keys()
            if f not in EXCLUDED_FROM_COUNT
        ]
        fields_expected = len(countable_fields)
        fields_extracted = 0

        # Validate each field
        for field_name in schema_template.keys():
            raw_value = raw_data.get(field_name)

            if field_name in EXCLUDED_FROM_COUNT:
                cleaned_data[field_name] = raw_value
                continue

            if raw_value is None:
                cleaned_data[field_name] = None
                continue

            cleaned_value, field_errors = self._validate_field(field_name, raw_value)

            if field_errors:
                errors.extend(field_errors)
                cleaned_data[field_name] = None
            else:
                cleaned_data[field_name] = cleaned_value
                fields_extracted += 1

        # Calculate coverage and determine status
        coverage = (
            fields_extracted / fields_expected
            if fields_expected > 0
            else 0.0
        )

        pass_threshold = settings.VALIDATION_PASS_THRESHOLD
        partial_threshold = settings.VALIDATION_PARTIAL_THRESHOLD

        if coverage >= pass_threshold:
            status = "passed"
            is_valid = True
            confidence_score = round(coverage * 0.95, 2)

        elif coverage >= partial_threshold:
            status = "partial"
            is_valid = True
            confidence_score = round(coverage * 0.70, 2)

        else:
            status = "failed"
            is_valid = False
            confidence_score = round(coverage * 0.50, 2)
            errors.append(
                f"Only {fields_extracted}/{fields_expected} fields extracted "
                f"({coverage:.0%}). Minimum required: {int(partial_threshold * 100)}%."
            )

        logger.info(
            "Validation %s: %d/%d fields (%.0f%%), confidence=%.2f, subtype=%s",
            status,
            fields_extracted,
            fields_expected,
            coverage * 100,
            confidence_score,
            equipment_sub_type
        )

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            cleaned_data=cleaned_data,
            errors=errors,
            confidence_score=confidence_score,
            fields_extracted=fields_extracted,
            fields_expected=fields_expected
        )

    # ==========================================================================
    # FIELD VALIDATION
    # ==========================================================================
    
    def _validate_field(self, field_name: str, raw_value: Any) -> tuple[Any, list[str]]:
        """Route field to appropriate validator based on type detection"""
        
        # Internal metadata should not be validated as business fields
        if field_name in INTERNAL_METADATA_FIELDS:
            return raw_value, []

        # RAW fields must always be strings
        if self._is_raw_field(field_name):
            return self._validate_string(field_name, raw_value)

        # Preserve structured fields if present
        if isinstance(raw_value, dict):
            return self._validate_object(field_name, raw_value)

        if isinstance(raw_value, list):
            return self._validate_list(field_name, raw_value)

        if self._is_power_field(field_name):
            return self._validate_power(field_name, raw_value)
        elif self._is_voltage_field(field_name):
            return self._validate_voltage(field_name, raw_value)
        elif self._is_current_field(field_name):
            return self._validate_current(field_name, raw_value)
        elif self._is_efficiency_field(field_name):
            return self._validate_efficiency(field_name, raw_value)
        elif self._is_count_field(field_name):
            return self._validate_integer(field_name, raw_value)
        elif self._is_boolean_field(field_name):
            return self._validate_boolean(field_name, raw_value)
        elif self._is_temperature_field(field_name):
            return self._validate_temperature_coefficient(field_name, raw_value)
        else:
            return self._validate_string(field_name, raw_value)

    # ========== VALIDATORS ==========

    def _validate_power(self, field_name: str, raw_value) -> tuple:
        """Validate power in Watts"""
        value = self._extract_numeric(raw_value)
        if value is None:
            return None, [f"{field_name}: could not extract numeric from '{raw_value}'"]

        if isinstance(raw_value, str) and "kw" in raw_value.lower():
            value = value * 1000

        if value <= 0:
            return None, [f"{field_name}: must be positive, got {value}"]

        if value > 1_000_000:
            return None, [f"{field_name}: {value}W seems unrealistically large"]

        return int(value) if value.is_integer() else value, []

    def _validate_voltage(self, field_name: str, raw_value) -> tuple:
        """Validate voltage (supports ranges like 208/240 and 211-240-264)"""
        if isinstance(raw_value, str):
            cleaned = raw_value.strip()
            cleaned = re.sub(r"\s+", " ", cleaned)

            # Allow range strings like "208/240" or "211-240-264"
            if "-" in cleaned or "/" in cleaned:
                return cleaned, []

        value = self._extract_numeric(raw_value)
        if value is None:
            return None, [f"{field_name}: could not extract voltage from '{raw_value}'"]

        if value <= 0:
            return None, [f"{field_name}: must be positive, got {value}"]

        if value > 2000:
            return None, [f"{field_name}: {value}V seems unrealistically large"]

        return int(value) if value.is_integer() else value, []

    def _validate_current(self, field_name: str, raw_value) -> tuple:
        """Validate current in Amperes"""
        value = self._extract_numeric(raw_value)
        if value is None:
            return None, [f"{field_name}: could not extract current from '{raw_value}'"]

        if value <= 0:
            return None, [f"{field_name}: must be positive, got {value}"]

        if value > 2000:
            return None, [f"{field_name}: {value}A seems unrealistically large"]

        return int(value) if value.is_integer() else value, []

    def _validate_efficiency(self, field_name: str, raw_value) -> tuple:
        """Validate efficiency as percentage (0-100)"""
        value = self._extract_numeric(raw_value)
        if value is None:
            return None, [f"{field_name}: could not extract efficiency from '{raw_value}'"]

        if not (0 < value <= 100):
            return None, [f"{field_name}: efficiency must be 0-100, got {value}"]

        return int(value) if value.is_integer() else value, []

    def _validate_integer(self, field_name: str, raw_value) -> tuple:
        """Validate integer count fields"""
        value = self._extract_numeric(raw_value)
        if value is None:
            return None, [f"{field_name}: expected integer, got '{raw_value}'"]

        value = int(value)
        if value < 0:
            return None, [f"{field_name}: must be non-negative, got {value}"]

        return value, []

    def _validate_boolean(self, field_name: str, raw_value) -> tuple:
        """Validate boolean fields"""
        if isinstance(raw_value, bool):
            return raw_value, []

        if isinstance(raw_value, str):
            lower = raw_value.lower().strip()
            if lower in ("true", "yes", "1", "y"):
                return True, []
            if lower in ("false", "no", "0", "n"):
                return False, []

        if raw_value in (1, 0):
            return bool(raw_value), []

        return None, [f"{field_name}: expected boolean, got '{raw_value}'"]

    def _validate_temperature_coefficient(self, field_name: str, raw_value) -> tuple:
        """Validate temperature coefficient (-5 to 5)"""
        value = self._extract_numeric(raw_value)
        if value is None:
            return None, [f"{field_name}: could not extract coefficient from '{raw_value}'"]

        if not (-5.0 <= value <= 5.0):
            return None, [f"{field_name}: {value} outside expected range -5.0 to 5.0"]

        return value, []

    def _validate_string(self, field_name: str, raw_value) -> tuple:
        """Validate string fields"""
        if raw_value is None:
            return None, []

        value = str(raw_value).strip()
        if len(value) == 0:
            return None, [f"{field_name}: empty string"]

        if len(value) > 1000:
            return None, [f"{field_name}: string too long ({len(value)} chars)"]

        return value, []

    def _validate_object(self, field_name: str, raw_value) -> tuple:
        """Validate object/dict fields"""
        if not isinstance(raw_value, dict):
            return None, [f"{field_name}: expected object, got '{type(raw_value).__name__}'"]

        if not raw_value:
            return None, [f"{field_name}: empty object"]

        return raw_value, []

    def _validate_list(self, field_name: str, raw_value) -> tuple:
        """Validate list fields"""
        if not isinstance(raw_value, list):
            return None, [f"{field_name}: expected list, got '{type(raw_value).__name__}'"]

        if len(raw_value) == 0:
            return None, [f"{field_name}: empty list"]

        return raw_value, []

    # ==========================================================================
    # HELPERS
    # ==========================================================================
    
    def _extract_numeric(self, raw_value) -> Optional[float]:
        """Extract numeric value from various formats"""
        if raw_value is None:
            return None

        if isinstance(raw_value, (int, float)):
            return float(raw_value)

        if isinstance(raw_value, str):
            text = raw_value.replace(",", "").strip()

            match = re.search(r"-?\d+\.?\d*", text)
            if match:
                try:
                    return float(match.group())
                except ValueError:
                    return None

        return None

    # ==========================================================================
    # FIELD TYPE DETECTION
    # ==========================================================================
    
    def _is_raw_field(self, name: str) -> bool:
        """Raw fields always validated as strings"""
        return name.endswith("_raw")

    def _is_power_field(self, name: str) -> bool:
        """Power fields in Watts"""
        return (
            not self._is_raw_field(name) and
            (
                name.endswith("_w") or
                "wattage" in name or
                ("power" in name and "powerwall" not in name.lower())
            )
        )

    def _is_voltage_field(self, name: str) -> bool:
        """Voltage fields in Volts"""
        return not self._is_raw_field(name) and (
            name.endswith("_v") or "voltage" in name
        )

    def _is_current_field(self, name: str) -> bool:
        """Current fields in Amperes"""
        return not self._is_raw_field(name) and (
            name.endswith("_a") or "current" in name
        )

    def _is_efficiency_field(self, name: str) -> bool:
        """Efficiency fields as percentage"""
        return not self._is_raw_field(name) and (
            name.endswith("_pct") or "efficiency" in name
        )

    def _is_count_field(self, name: str) -> bool:
        """Integer count fields"""
        return not self._is_raw_field(name) and any(
            k in name for k in ["channels", "quantity", "count", "mppt"]
        )

    def _is_boolean_field(self, name: str) -> bool:
        """Boolean fields"""
        return not self._is_raw_field(name) and (
            name.startswith("has_") or
            name.startswith("is_") or
            name.startswith("supports_")
        )

    def _is_temperature_field(self, name: str) -> bool:
        """Temperature coefficient fields"""
        return not self._is_raw_field(name) and "temperature_coefficient" in name
