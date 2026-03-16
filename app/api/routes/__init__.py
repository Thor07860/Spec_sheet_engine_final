# ==============================================================================
# api/routes/__init__.py
# ------------------------------------------------------------------------------
# Central export for all route routers.
# main.py imports from here to register all routes in one place.
# ==============================================================================

from app.api.routes.equipment_routes import router as equipment_router
from app.api.routes.job_routes import router as job_router
from app.api.routes.source_routes import router as source_router
from app.api.routes.health_routes import router as health_router

__all__ = [
    "equipment_router",
    "job_router",
    "source_router",
    "health_router",
]