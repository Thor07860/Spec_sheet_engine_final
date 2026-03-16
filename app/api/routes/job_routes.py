# ==============================================================================
# api/routes/job_routes.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Endpoints for checking extraction job status and history.
#
# ENDPOINTS:
#   GET /jobs/{job_id}   → get status and result of a specific job
#
# WHY THESE ENDPOINTS EXIST:
#   Every POST /equipment creates an ExtractionJob in the database.
#   If PMS wants to know what happened with a past extraction
#   (what URL was used, did matching succeed, what did Gemini return),
#   these endpoints provide that visibility.
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.schemas.job_schema import JobStatusResponse

import logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


# ==============================================================================
# GET /jobs/{job_id}
# ------------------------------------------------------------------------------
# Returns full status and details of a specific extraction job.
#
# Example: GET /jobs/abc12345-...
#
# Response includes:
#   - Current status (pending/processing/completed/failed)
#   - What model was matched
#   - Which URL was selected
#   - When it completed
#   - Error message if failed
# ==============================================================================
@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get job status",
    description="Returns status and details of an extraction job by its UUID."
)
def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    from app.repositories.job_repository import JobRepository

    repo = JobRepository(db)
    job = repo.get_by_id(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    return job