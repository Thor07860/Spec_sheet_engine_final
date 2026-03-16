# ==============================================================================
# schemas/job_schema.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Contains schemas related to extraction job tracking.
#   An extraction job is created every time PMS requests equipment specs.
#   These schemas represent the job lifecycle responses.
#
# WHY SEPARATE FROM response_schema.py:
#   Job responses have a different shape from equipment responses.
#   They represent PROCESS state (pending, processing, completed, failed)
#   rather than DATA state (the actual specs).
#   Keeping them separate makes each file focused and easy to find.
# ==============================================================================

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

from app.models.equipment_model import JobStatus, MatchType

# Import equipment response for embedding in completed job response
from app.schemas.response_schema import EquipmentResponse


# ==============================================================================
# ExtractionJobResponse
# ------------------------------------------------------------------------------
# The main response when an extraction is triggered or status is checked.
#
# THREE POSSIBLE STATES:
#
# 1. Just started (status=processing):
#    { "job_id": "abc...", "status": "processing", "message": "...", "data": null }
#
# 2. Completed (status=completed):
#    { "job_id": "abc...", "status": "completed", "data": { full equipment JSON } }
#
# 3. Failed (status=failed):
#    { "job_id": "abc...", "status": "failed", "error": "No trusted source found" }
#
# 4. Cache hit (status=cached):
#    { "job_id": null, "status": "cached", "data": { full equipment JSON } }
# ==============================================================================
class ExtractionJobResponse(BaseModel):

    # UUID of the extraction job — null only on cache hits (no job created)
    job_id: Optional[UUID] = None

    # Current lifecycle status of the job
    status: JobStatus

    # Human-readable message explaining what happened
    # Examples:
    #   "Extraction completed for SolarEdge SE7600H-US"
    #   "No trusted source found for model SE9999"
    #   "Returned from cache"
    message: str

    # Full equipment data — only present when status = completed or cached
    data: Optional[EquipmentResponse] = None

    # Error detail — only present when status = failed
    error: Optional[str] = None

    class Config:
        from_attributes = True


# ==============================================================================
# JobStatusResponse
# ------------------------------------------------------------------------------
# Lightweight status check response.
# Used when PMS polls GET /jobs/{job_id} to check progress.
#
# WHY SEPARATE FROM ExtractionJobResponse:
#   ExtractionJobResponse is for the initial POST response.
#   JobStatusResponse is for subsequent GET status checks —
#   it includes more detail about what stage the job is at.
# ==============================================================================
class JobStatusResponse(BaseModel):

    job_id: UUID
    status: JobStatus

    # Input that was requested
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    equipment_sub_type: Optional[str] = None

    # Matching result
    matched_model: Optional[str] = None
    match_type: Optional[MatchType] = None

    # Which URL was selected for extraction
    selected_source_url: Optional[str] = None

    # Link to resulting equipment record (present when completed)
    equipment_id: Optional[UUID] = None

    # Error message (present when failed)
    error_message: Optional[str] = None

    # Timestamps
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True