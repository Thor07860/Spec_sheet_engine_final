# ==============================================================================
# repositories/trusted_source_repository.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   CRUD operations for the TrustedSource table ONLY.
#   Used by the source validation service to score and filter Serper results.
#   Only domains with trust_score >= MIN_TRUST_SCORE are used for extraction.
#
# RULE: This file only touches the TrustedSource table.
# ==============================================================================

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List

from app.models.equipment_model import TrustedSource

import logging
logger = logging.getLogger(__name__)


class TrustedSourceRepository:

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------------------------------
    # get_by_domain()
    # --------------------------------------------------------------------------
    # Look up trust score for a specific domain.
    # Called for every URL returned by Serper to score it.
    #
    # Returns None if domain is not in our list → treated as untrusted (score=0)
    # --------------------------------------------------------------------------
    def get_by_domain(self, domain: str) -> Optional[TrustedSource]:

        return (
            self.db.query(TrustedSource)
            .filter(
                and_(
                    TrustedSource.domain.ilike(domain),
                    TrustedSource.is_active == True     # ignore deactivated domains
                )
            )
            .first()
        )

    # --------------------------------------------------------------------------
    # get_all_active()
    # --------------------------------------------------------------------------
    # Fetch all active trusted sources for a given country.
    # Used to build domain list for source validation.
    #
    # Default country = "US" because our scope is USA only.
    # --------------------------------------------------------------------------
    def get_all_active(self, country: str = "US") -> List[TrustedSource]:

        return (
            self.db.query(TrustedSource)
            .filter(
                and_(
                    TrustedSource.is_active == True,
                    TrustedSource.country == country
                )
            )
            .order_by(TrustedSource.trust_score.desc())  # highest trust first
            .all()
        )

    # --------------------------------------------------------------------------
    # create()
    # --------------------------------------------------------------------------
    # Add a new trusted domain.
    # Called by admin endpoint when a new manufacturer is added.
    # No code redeploy needed — just insert a row.
    # --------------------------------------------------------------------------
    def create(self, data: dict) -> TrustedSource:

        source = TrustedSource(**data)
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)

        logger.info("Added trusted source: %s", data.get("domain"))
        return source

    # --------------------------------------------------------------------------
    # deactivate()
    # --------------------------------------------------------------------------
    # Soft-delete a domain by setting is_active=False.
    #
    # WHY NOT HARD DELETE:
    #   Deactivating is reversible — deleting loses history permanently.
    #   You can reactivate with a single DB update if needed.
    # --------------------------------------------------------------------------
    def deactivate(self, domain: str) -> bool:

        source = (
            self.db.query(TrustedSource)
            .filter(TrustedSource.domain.ilike(domain))
            .first()
        )

        if not source:
            return False

        source.is_active = False
        self.db.commit()

        logger.info("Deactivated trusted source: %s", domain)
        return True