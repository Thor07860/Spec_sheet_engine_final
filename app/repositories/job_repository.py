# ==============================================================================
# repositories/job_repository.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   CRUD operations for the ExtractionJob table ONLY.
#   Every extraction request creates a job row here.
#   Tracks the full lifecycle: PENDING → PROCESSING → COMPLETED / FAILED
#
# RULE: This file only touches the ExtractionJob table.
# ==============================================================================

from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.models.equipment_model import ExtractionJob, JobStatus, MatchType

import logging
logger = logging.getLogger(__name__)


class JobRepository:

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------------------------------
    # create()
    # --------------------------------------------------------------------------
    # Create a new extraction job when a request arrives from PMS.
    # Initial status is always PENDING — the worker changes it from there.
    # --------------------------------------------------------------------------
    def create(
        self,
        manufacturer: str,
        model: str,
        equipment_type: str,
        equipment_sub_type: str
    ) -> ExtractionJob:

        job = ExtractionJob(
            manufacturer=manufacturer,
            model=model,
            equipment_type=equipment_type,
            equipment_sub_type=equipment_sub_type,
            status=JobStatus.PENDING        # always starts as pending
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        logger.info(
            "Created job %s for %s %s", job.id, manufacturer, model
        )
        return job

    # --------------------------------------------------------------------------
    # get_by_id()
    # --------------------------------------------------------------------------
    # Fetch a job by UUID — used by PMS to poll job status.
    # --------------------------------------------------------------------------
    def get_by_id(self, job_id: UUID) -> Optional[ExtractionJob]:

        return (
            self.db.query(ExtractionJob)
            .filter(ExtractionJob.id == job_id)
            .first()
        )

    # --------------------------------------------------------------------------
    # update_status()
    # --------------------------------------------------------------------------
    # Move a job through its lifecycle stages.
    #
    # Called three times during a typical successful extraction:
    #   1. PENDING     → PROCESSING  (worker picks up job)
    #   2. PROCESSING  → COMPLETED   (specs saved to Equipment table)
    #
    # Called once on failure:
    #   1. PROCESSING  → FAILED      (with error_message explaining why)
    #
    # completed_at is automatically set when status reaches a terminal state.
    # Terminal states = COMPLETED or FAILED (job will never change again).
    # --------------------------------------------------------------------------
    def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        error_message: Optional[str] = None,
        matched_model: Optional[str] = None,
        match_type: Optional[MatchType] = None,
        selected_source_url: Optional[str] = None,
        equipment_id: Optional[UUID] = None
    ) -> Optional[ExtractionJob]:

        job = self.get_by_id(job_id)

        if not job:
            logger.warning("Job %s not found for status update", job_id)
            return None

        # Update status and any provided optional fields
        job.status = status

        if error_message:
            job.error_message = error_message

        if matched_model:
            job.matched_model = matched_model

        if match_type:
            job.match_type = match_type

        if selected_source_url:
            job.selected_source_url = selected_source_url

        if equipment_id:
            job.equipment_id = equipment_id

        # Set completed_at only when job reaches a terminal state
        # WHY: Only set once — when job can no longer change status
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(job)

        logger.info("Job %s → status=%s", job_id, status)
        return job