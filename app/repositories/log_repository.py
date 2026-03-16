# ==============================================================================
# repositories/log_repository.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   CRUD operations for MatchLog and ExtractionLog tables ONLY.
#   These are write-once audit logs — never updated after creation.
#
# WHY WRITE-ONCE:
#   Logs exist to answer "what happened?" when something goes wrong.
#   If logs could be modified, they lose their value as audit records.
#   Write once, read many — that is the rule for logs.
#
# RULE: This file only touches MatchLog and ExtractionLog tables.
# ==============================================================================

from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID

from app.models.equipment_model import MatchLog, ExtractionLog, MatchType

import logging
logger = logging.getLogger(__name__)


class LogRepository:

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------------------------------
    # create_match_log()
    # --------------------------------------------------------------------------
    # Record the fuzzy matching decision for a job.
    #
    # EXAMPLE SCENARIO:
    #   PMS sent:        "SE7600"
    #   Serper found:    "SE7600H-US"
    #   Similarity:      94.5%
    #   Decision:        APPROXIMATE — accepted (above 80% threshold)
    #
    # WHY LOG THIS:
    #   If wrong specs are returned, you trace it here.
    #   A bad fuzzy match is the most common cause of wrong data.
    # --------------------------------------------------------------------------
    def create_match_log(
        self,
        job_id: UUID,
        input_model: str,
        matched_model: Optional[str],
        similarity_score: Optional[float],
        match_type: MatchType
    ) -> MatchLog:

        log = MatchLog(
            job_id=job_id,
            input_model=input_model,
            matched_model=matched_model,
            similarity_score=similarity_score,
            match_type=match_type
        )

        self.db.add(log)
        self.db.commit()

        logger.info(
            "Match log: input=%s matched=%s score=%s type=%s",
            input_model, matched_model, similarity_score, match_type
        )
        return log

    # --------------------------------------------------------------------------
    # create_extraction_log()
    # --------------------------------------------------------------------------
    # Record exactly what Gemini returned and whether it passed validation.
    #
    # WHY LOG RAW LLM RESPONSE:
    #   This is the most important debugging tool in the whole system.
    #   If extraction fails, validation_errors tells you exactly why.
    #   If Gemini hallucinated, raw_llm_response shows you what it said.
    #   Without this log, debugging extraction failures is nearly impossible.
    #
    # validation_status values:
    #   "passed"  → all required fields valid, data saved to Equipment table
    #   "partial" → some fields valid, some null — saved with lower confidence
    #   "failed"  → too many invalid fields, data NOT saved
    # --------------------------------------------------------------------------
    def create_extraction_log(
        self,
        job_id: UUID,
        raw_llm_response: Optional[dict],
        validated_data: Optional[dict],
        validation_status: str,
        validation_errors: Optional[List[str]],
        fields_extracted: Optional[int],
        fields_expected: Optional[int]
    ) -> ExtractionLog:

        log = ExtractionLog(
            job_id=job_id,
            raw_llm_response=raw_llm_response,
            validated_data=validated_data,
            validation_status=validation_status,
            validation_errors=validation_errors or [],  # never store None — use []
            fields_extracted=fields_extracted,
            fields_expected=fields_expected
        )

        self.db.add(log)
        self.db.commit()

        logger.info(
            "Extraction log: job=%s status=%s fields=%s/%s",
            job_id, validation_status, fields_extracted, fields_expected
        )
        return log