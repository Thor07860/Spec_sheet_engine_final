# ==============================================================================
# schemas/health_schema.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Health check response schema.
#   The /health endpoint returns this so load balancers and monitoring
#   tools know if the application and its dependencies are alive.
#
# WHY A SEPARATE FILE:
#   Health check has nothing to do with equipment data.
#   Keeping it isolated means you can find and update it instantly.
#
# WHO CALLS /health:
#   - AWS load balancers (to decide whether to route traffic here)
#   - Kubernetes liveness/readiness probes
#   - Uptime monitoring tools (Datadog, Grafana, etc.)
# ==============================================================================

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """
    System health check response.

    status = "healthy"  → all services running normally
    status = "degraded" → app is up but Redis or DB has issues
                          (app still works, just slower — no cache)

    Example response:
    {
        "status": "healthy",
        "database": "connected",
        "redis": "connected",
        "version": "1.0.0"
    }
    """

    # Overall system health: "healthy" or "degraded"
    status: str

    # PostgreSQL connection status: "connected" or "disconnected"
    database: str

    # Redis connection status: "connected" or "disconnected"
    redis: str

    # Application version — useful to confirm deployments went through
    version: str


class SerperCreditsResponse(BaseModel):
    """
    Serper API credit status response.

    status = "ok"       → sufficient credits (> 100)
    status = "warning"  → low credits (100-10)
    status = "critical" → critically low credits (<= 10)
    status = "error"    → cannot reach Serper API

    Example response:
    {
        "success": true,
        "credits_remaining": 245,
        "credits_used": 755,
        "credits_total": 1000,
        "status": "ok",
        "message": "Serper API credits: 245 remaining"
    }
    """

    # Whether the API call succeeded
    success: bool

    # Credits remaining
    credits_remaining: int

    # Total credits used in billing period
    credits_used: int

    # Total credits allocated
    credits_total: int

    # Status: "ok" | "warning" | "critical" | "error"
    status: str

    # Human-readable message
    message: str