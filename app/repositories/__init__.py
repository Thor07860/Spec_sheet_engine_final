# ==============================================================================
# repositories/__init__.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Central export point for all repository classes.
#
# HOW TO USE IN OTHER FILES:
#   from app.repositories import (
#       EquipmentRepository,
#       JobRepository,
#       SourceRepository,
#       TrustedSourceRepository,
#       TemplateRepository,
#       LogRepository,
#   )
#
# HOW TO ADD A NEW REPOSITORY IN THE FUTURE:
#   1. Create the file: repositories/new_thing_repository.py
#   2. Add import below
#   3. Add to __all__
#   Done — everything imports from here cleanly.
# ==============================================================================

from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.job_repository import JobRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.trusted_source_repository import TrustedSourceRepository
from app.repositories.template_repository import TemplateRepository
from app.repositories.log_repository import LogRepository

__all__ = [
    "EquipmentRepository",
    "JobRepository",
    "SourceRepository",
    "TrustedSourceRepository",
    "TemplateRepository",
    "LogRepository",
]