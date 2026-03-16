# ==============================================================================
# services/__init__.py
# ------------------------------------------------------------------------------
# Central export point for all service classes.
#
# HOW TO USE IN ROUTES:
#   from app.services import EquipmentService
#
# HOW TO ADD A NEW SERVICE IN THE FUTURE:
#   1. Create services/new_service.py
#   2. Add import below
#   3. Add to __all__
# ==============================================================================

from app.services.equipment_service import EquipmentService
from app.services.serper_service import SerperService
from app.services.extraction import ExtractionService  # Now from extraction/ submodule
from app.services.matching_service import MatchingService
from app.services.validation import ValidationService  # Now from validation/ submodule

__all__ = [
    "EquipmentService",
    "SerperService",
    "ExtractionService",
    "MatchingService",
    "ValidationService",
]