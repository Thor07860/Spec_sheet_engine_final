# ==============================================================================
# services/validation/__init__.py
# ==============================================================================
# Validation module: Field and cross-field validation for extracted specs
# ==============================================================================

from .validation_service import ValidationService, ValidationResult
from .cross_field_validator import CrossFieldValidator

__all__ = [
    "ValidationService",
    "ValidationResult",
    "CrossFieldValidator"
]
