# ==============================================================================
# api/routes/health_routes.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   System health check endpoint.
#   Verifies PostgreSQL and Redis connections are alive.
#
# ENDPOINTS:
#   GET /health  → returns system health status
#
# WHO CALLS THIS:
#   - Load balancers (to decide whether to route traffic here)
#   - Monitoring tools (Datadog, Grafana, uptime monitors)
#   - Your own scripts to verify the system is up
#
# RESPONSE:
#   status = "healthy"  → all systems running normally
#   status = "degraded" → app is up but a dependency has issues
#                         (still returns 200 — app can still serve cached data)
# ==============================================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.redis import redis_client
from app.core.config import settings
from app.schemas.health_schema import HealthResponse, SerperCreditsResponse
from app.services.serper_service import SerperService

import logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/health",
    tags=["Health"]
)


# ==============================================================================
# GET /health
# ==============================================================================
@router.get(
    "/",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the health status of the application and its dependencies."
)
def health_check(db: Session = Depends(get_db)):

    # --- Check PostgreSQL ---
    # Run a trivial query — if it works, DB is connected
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error("Database health check failed: %s", str(e))
        db_status = "disconnected"

    # --- Check Redis ---
    # redis_client.ping() returns True if Redis is alive
    try:
        redis_status = "connected" if redis_client.ping() else "disconnected"
    except Exception as e:
        logger.error("Redis health check failed: %s", str(e))
        redis_status = "disconnected"

    # --- Overall status ---
    # healthy  = all dependencies connected
    # degraded = at least one dependency is down
    # App still runs degraded — it falls through to DB if Redis is down
    overall = (
        "healthy"
        if db_status == "connected" and redis_status == "connected"
        else "degraded"
    )

    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        version=settings.APP_VERSION
    )


# ==============================================================================
# GET /health/serper
# ==============================================================================
@router.get(
    "/serper",
    response_model=SerperCreditsResponse,
    summary="Serper API credit status",
    description="Returns the current Serper API credit balance and status."
)
def check_serper_credits(db: Session = Depends(get_db)):
    """
    Check Serper API credit balance.
    
    Returns:
        - success: True if API call succeeded
        - credits_remaining: Credits available for searches
        - credits_used: Total credits used this billing period
        - credits_total: Total credits allocated
        - status: "ok" (>100), "warning" (10-100), "critical" (≤10), or "error"
        - message: Human-readable status message
    
    Usage:
        GET /health/serper
    
    Example Response:
    {
        "success": true,
        "credits_remaining": 245,
        "credits_used": 755,
        "credits_total": 1000,
        "status": "ok",
        "message": "Serper API credits: 245 remaining"
    }
    """
    serper_service = SerperService(db)
    return serper_service.get_api_credits()