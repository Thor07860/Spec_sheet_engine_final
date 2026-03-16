# ==============================================================================
# services/validation_service.py (BACKWARD COMPATIBILITY SHIM)
# ==============================================================================
# This file provides backward compatibility for old imports:
#   from app.services.validation_service import ValidationService
#
# New code should use:
#   from app.services.validation import ValidationService
# ==============================================================================

# Re-export from new location
from app.services.validation.validation_service import ValidationService, ValidationResult
from app.services.validation.cross_field_validator import CrossFieldValidator

__all__ = ["ValidationService", "ValidationResult", "CrossFieldValidator"]
