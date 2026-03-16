# ==============================================================================
# schemas/__init__.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Re-exports all schemas from one central place.
#
# WHY THIS IS IMPORTANT:
#   Without this, every file that needs a schema must do:
#     from app.schemas.request_schema import EquipmentRequest
#     from app.schemas.response_schema import EquipmentResponse
#     from app.schemas.job_schema import ExtractionJobResponse
#
#   With this __init__.py, any file can do:
#     from app.schemas import EquipmentRequest, EquipmentResponse
#
#   Much cleaner. And if you ever rename or move a schema file,
#   you only update this one file — nothing else breaks.
#
# HOW TO ADD A NEW SCHEMA IN THE FUTURE:
#   1. Create the schema in the appropriate file
#      (request_schema.py, response_schema.py, etc.)
#   2. Add it to the import list below
#   That's it.
# ==============================================================================

# Request schemas — what the API receives
from app.schemas.request_schema import (
    EquipmentRequest,
    TrustedSourceCreate,
    EquipmentListRequest,
)

# Response schemas — what the API sends back
from app.schemas.response_schema import (
    EquipmentResponse,
    EquipmentSearchResponse,
    EquipmentListResponse,
    TrustedSourceResponse,
    TemplateResponse,
)

# Job schemas — extraction job lifecycle
from app.schemas.job_schema import (
    ExtractionJobResponse,
    JobStatusResponse,
)

# Health check schema
from app.schemas.health_schema import HealthResponse


# This list defines what gets exported when someone does:
# from app.schemas import *
__all__ = [
    # Requests
    "EquipmentRequest",
    "TrustedSourceCreate",
    "EquipmentListRequest",
    # Responses
    "EquipmentResponse",
    "EquipmentSearchResponse",
    "EquipmentListResponse",
    "TrustedSourceResponse",
    "TemplateResponse",
    # Jobs
    "ExtractionJobResponse",
    "JobStatusResponse",
    # Health
    "HealthResponse",
]