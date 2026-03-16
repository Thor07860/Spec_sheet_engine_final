# ==============================================================================
# api/routes/source_routes.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Endpoints for managing trusted source domains.
#   Add, list, and deactivate trusted manufacturer domains.
#
# ENDPOINTS:
#   GET    /sources           → list all active trusted sources
#   POST   /sources           → add a new trusted domain
#   DELETE /sources/{domain}  → deactivate a domain
#
# WHY THESE ENDPOINTS EXIST:
#   New manufacturers enter the US solar market regularly.
#   Instead of redeploying code to add a new trusted domain,
#   an admin just calls POST /sources — zero code change.
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.schemas.request_schema import TrustedSourceCreate
from app.schemas.response_schema import TrustedSourceResponse

import logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sources",
    tags=["Trusted Sources"]
)


# ==============================================================================
# GET /sources
# ------------------------------------------------------------------------------
# List all active trusted source domains.
# ==============================================================================
@router.get(
    "/",
    response_model=List[TrustedSourceResponse],
    status_code=status.HTTP_200_OK,
    summary="List trusted sources",
    description="Returns all active trusted domains sorted by trust score."
)
def list_trusted_sources(
    db: Session = Depends(get_db)
):
    from app.repositories.trusted_source_repository import TrustedSourceRepository

    repo = TrustedSourceRepository(db)
    return repo.get_all_active(country="US")


# ==============================================================================
# POST /sources
# ------------------------------------------------------------------------------
# Add a new trusted domain.
#
# Example body:
# {
#     "domain": "apsystems.com",
#     "trust_score": 90,
#     "country": "US",
#     "source_type": "manufacturer"
# }
# ==============================================================================
@router.post(
    "/",
    response_model=TrustedSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add trusted source",
    description="Adds a new trusted domain for spec sheet discovery."
)
def add_trusted_source(
    request: TrustedSourceCreate,
    db: Session = Depends(get_db)
):
    from app.repositories.trusted_source_repository import TrustedSourceRepository

    repo = TrustedSourceRepository(db)

    # Create the new trusted source
    source = repo.create({
        "domain": request.domain,
        "trust_score": request.trust_score,
        "country": request.country,
        "source_type": request.source_type,
        "is_active": True
    })

    logger.info("Added trusted source: %s", request.domain)
    return source


# ==============================================================================
# DELETE /sources/{domain}
# ------------------------------------------------------------------------------
# Deactivate a trusted domain (soft delete — reversible).
#
# Example: DELETE /sources/manualslib.com
# ==============================================================================
@router.delete(
    "/{domain}",
    status_code=status.HTTP_200_OK,
    summary="Deactivate trusted source",
    description="Deactivates a trusted domain. It will no longer be used for extraction."
)
def deactivate_trusted_source(
    domain: str,
    db: Session = Depends(get_db)
):
    from app.repositories.trusted_source_repository import TrustedSourceRepository

    repo = TrustedSourceRepository(db)
    success = repo.deactivate(domain)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain '{domain}' not found in trusted sources"
        )

    return {
        "status": "success",
        "message": f"Domain '{domain}' deactivated successfully"
    }