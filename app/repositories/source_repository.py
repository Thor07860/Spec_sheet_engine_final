# ==============================================================================
# repositories/source_repository.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   CRUD operations for the EquipmentSource table ONLY.
#   Stores all URLs found by Serper for each extraction job.
#   One job → many sources. Only one source per job is marked is_selected=True.
#
# RULE: This file only touches the EquipmentSource table.
# ==============================================================================

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
from uuid import UUID

from app.models.equipment_model import EquipmentSource

import logging
logger = logging.getLogger(__name__)


class SourceRepository:

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------------------------------
    # bulk_create()
    # --------------------------------------------------------------------------
    # Save all URLs found by Serper in ONE database operation.
    #
    # WHY BULK INSERT:
    #   Serper returns ~5 results per search.
    #   Inserting one at a time = 5 separate DB round-trips.
    #   add_all() batches them into one — much faster.
    #
    # Each source dict must contain:
    #   url, domain, trust_score, source_type
    # --------------------------------------------------------------------------
    def bulk_create(
        self,
        job_id: UUID,
        sources: List[dict]
    ) -> List[EquipmentSource]:

        source_objects = [
            EquipmentSource(
                job_id=job_id,
                url=s.get("url"),
                domain=s.get("domain"),
                trust_score=s.get("trust_score", 0),
                source_type=s.get("source_type", "unknown"),
                is_selected=False           # none selected yet
            )
            for s in sources
        ]

        self.db.add_all(source_objects)    # batch insert — one DB round-trip
        self.db.commit()

        logger.info("Saved %d sources for job %s", len(source_objects), job_id)
        return source_objects

    # --------------------------------------------------------------------------
    # mark_selected()
    # --------------------------------------------------------------------------
    # Mark one specific URL as the source actually used for extraction.
    # This is called after source validation picks the best trusted URL.
    # --------------------------------------------------------------------------
    def mark_selected(self, job_id: UUID, url: str) -> None:

        source = (
            self.db.query(EquipmentSource)
            .filter(
                and_(
                    EquipmentSource.job_id == job_id,
                    EquipmentSource.url == url
                )
            )
            .first()
        )

        if source:
            source.is_selected = True
            self.db.commit()
            logger.info("Marked selected source: %s", url)