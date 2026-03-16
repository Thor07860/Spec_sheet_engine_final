# ==============================================================================
# api/routes/equipment_routes.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Handles all HTTP endpoints related to equipment spec extraction.
#   This is what PMS calls to get equipment data.
#
# ENDPOINTS:
#   POST /equipment          → trigger extraction for a new equipment
#   GET  /equipment          → list all stored equipment (paginated)
#   GET  /equipment/{id}     → get one equipment record by UUID
#   DELETE /equipment/{id}   → delete an equipment record (admin)
#
# RULE:
#   Routes only handle HTTP concerns:
#     - Read request data
#     - Call the service
#     - Return the response
#   Routes NEVER contain business logic.
#   All logic lives in EquipmentService.
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Database session dependency
from app.core.database import get_db, SessionLocal

# Service — the only thing routes call
from app.services.equipment_service import EquipmentService

# Schemas — define request shape and response shape
from app.schemas.request_schema import EquipmentRequest, EquipmentBatchRequest, EquipmentListRequest
from app.schemas.response_schema import EquipmentResponse, EquipmentListResponse

import logging
logger = logging.getLogger(__name__)

# Create the router for equipment endpoints
# prefix="/equipment" means all routes here start with /equipment
# tags=["Equipment"] groups them in the auto-generated API docs at /docs
router = APIRouter(
    prefix="/equipment",
    tags=["Equipment"]
)


# ==============================================================================
# POST /equipment
# ==============================================================================
# UNIFIED ENDPOINT: Handles BOTH single and batch equipment extraction.
#
# MODE 1 (SINGLE): Pass one equipment item
# {
#     "manufacturer": "SolarEdge",
#     "model": "SE7600H-US",
#     "equipment_type": "inverter",
#     "equipment_sub_type": "solaredge_inverter"
# }
#
# MODE 2 (BATCH): Pass array of equipment items
# {
#     "equipments": [
#         { "manufacturer": "...", "model": "...", ... },
#         { "manufacturer": "...", "model": "...", ... },
#         ...
#     ]
# }
#
# Performance:
#   Single item: Cache/DB lookup only, ~200-500ms
#   Batch (26 items): ~35-45 seconds with 15 parallel workers
#
# Response:
#   200 → success (single item returns object, batch returns array)
#   422 → validation error
#   500 → internal error
# ==============================================================================
@router.post(
    "/",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Extract equipment specifications (Single or Batch)",
    description=(
        "Extract specs for one OR multiple equipment items. "
        "Single item: Pass manufacturer, model, equipment_type, equipment_sub_type. "
        "Batch: Pass {\"equipments\": [item1, item2, ...]} array. "
        "Batch mode uses 15 parallel workers."
    )
)
def extract_equipment(
    request: EquipmentRequest | EquipmentBatchRequest,
    db: Session = Depends(get_db)
):
    """
    Unified equipment extraction endpoint.
    Detects single vs batch mode automatically.
    
    ✅ SINGLE MODE: Process one equipment item
    ✅ BATCH MODE: Process multiple items with 15 parallel workers
    """

    # ========================================================================
    # DETECT MODE: Single vs Batch
    # ========================================================================
    is_batch = isinstance(request, EquipmentBatchRequest)

    if is_batch:
        # ====================================================================
        # BATCH MODE: Multiple equipments with parallel extraction
        # ====================================================================
        logger.info("━" * 80)
        logger.info("⚡ BATCH MODE: Processing %d equipment items (15 parallel workers)", len(request.equipments))
        logger.info("━" * 80)

        batch_start = time.time()
        
        # Thread-safe counter for tracking completion
        metrics_lock = Lock()
        completed_count = {"value": 0}

        def process_equipment_item(index: int, equipment_req):
            """
            Worker function: Process one equipment item
            Runs in background thread with its own DB session
            """
            item_start = time.time()
            item_desc = f"{equipment_req.manufacturer} {equipment_req.model}"
            
            logger.info(
                "  [Worker] Starting: %s (%s)",
                item_desc,
                equipment_req.equipment_sub_type
            )

            # IMPORTANT: every worker must use its own DB session.
            # SQLAlchemy sessions are not thread-safe.
            thread_db = SessionLocal()

            try:
                # Create service instance for this thread
                service = EquipmentService(thread_db)
                
                result = service.get_equipment_specs(
                    manufacturer=equipment_req.manufacturer,
                    model=equipment_req.model,
                    equipment_type=equipment_req.equipment_type,
                    equipment_sub_type=equipment_req.equipment_sub_type
                )

                item_elapsed = (time.time() - item_start) * 1000
                
                # Track completion
                with metrics_lock:
                    completed_count["value"] += 1
                    comp = completed_count["value"]
                
                if result.get("status") == "success":
                    logger.info(
                        "  ✅ [%d] %s | Time: %.0fms",
                        comp,
                        item_desc,
                        item_elapsed
                    )
                else:
                    logger.info(
                        "  ⚠️  [%d] %s | Time: %.0fms | Status: %s",
                        comp,
                        item_desc,
                        item_elapsed,
                        result.get("status", "unknown")
                    )

                return index, {
                    "manufacturer": equipment_req.manufacturer,
                    "model": equipment_req.model,
                    "equipment_type": equipment_req.equipment_type,
                    "equipment_sub_type": equipment_req.equipment_sub_type,
                    "result": result
                }

            except Exception as e:
                item_elapsed = (time.time() - item_start) * 1000
                with metrics_lock:
                    completed_count["value"] += 1
                    comp = completed_count["value"]
                
                logger.error(
                    "  ❌ [%d] %s | Time: %.0fms | Error: %s",
                    comp,
                    item_desc,
                    item_elapsed,
                    str(e)
                )

                return index, {
                    "manufacturer": equipment_req.manufacturer,
                    "model": equipment_req.model,
                    "equipment_type": equipment_req.equipment_type,
                    "equipment_sub_type": equipment_req.equipment_sub_type,
                    "result": {
                        "status": "failed",
                        "source": None,
                        "data": None,
                        "error": str(e)
                    }
                }
            
            finally:
                # CRITICAL: Close thread-local session
                thread_db.close()

        # ====================================================================
        # PARALLEL EXECUTION WITH 15 CONCURRENT WORKERS
        # ====================================================================
        results = [None] * len(request.equipments)
        
        with ThreadPoolExecutor(max_workers=15) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    process_equipment_item, 
                    i, 
                    equipment_req
                ): i
                for i, equipment_req in enumerate(request.equipments)
            }
            
            # Collect results as they complete
            for future in as_completed(futures):
                try:
                    index, result = future.result()
                    results[index] = result
                except Exception as e:
                    logger.error("Unexpected error in thread pool: %s", str(e))

        # ====================================================================
        # BATCH SUMMARY & METRICS
        # ====================================================================
        successful = sum(1 for r in results if r and r["result"]["status"] == "success")
        failed = len(results) - successful
        total_batch_ms = (time.time() - batch_start) * 1000

        logger.info("━" * 80)
        logger.info("📊 BATCH SUMMARY (15 WORKERS)")
        logger.info("  Items: %d/%d successful, %d failed", successful, len(results), failed)
        logger.info("  ⏱️  Time: %.0fms total (%.1fs)", total_batch_ms, total_batch_ms / 1000)
        logger.info("━" * 80)

        return {
            "status": "success",
            "mode": "batch",
            "batch_size": len(results),
            "successful": successful,
            "failed": failed,
            "results": results
        }

    else:
        # ====================================================================
        # SINGLE MODE: Process one equipment item
        # ====================================================================
        logger.info(
            "📦 SINGLE MODE: manufacturer=%s model=%s sub_type=%s",
            request.manufacturer, request.model, request.equipment_sub_type
        )

        # Initialize the service with the DB session
        service = EquipmentService(db)

        # Run the full pipeline — returns a result dict
        result = service.get_equipment_specs(
            manufacturer=request.manufacturer,
            model=request.model,
            equipment_type=request.equipment_type,
            equipment_sub_type=request.equipment_sub_type
        )

        # If extraction completely failed, return 422 with error detail
        # WHY 422: The request was valid but we couldn't process it
        if result["status"] == "failed":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Equipment extraction failed",
                    "error": result["error"]
                }
            )

        # Return the JSON response directly
        # The calculation engine and SLD generator will consume this
        return {
            "status": result["status"],
            "mode": "single",
            "source": result["source"],     # "cache" | "database" | "extracted"
            "data": result["data"]          # the actual equipment specs
        }


# ==============================================================================
# GET /equipment
# ------------------------------------------------------------------------------
# List all stored equipment with optional filters and pagination.
#
# Query parameters (all optional):
#   equipment_type     → filter by type e.g. "inverter"
#   equipment_sub_type → filter by sub-type e.g. "solaredge_inverter"
#   manufacturer       → filter by manufacturer e.g. "SolarEdge"
#   page               → page number (default 1)
#   page_size          → items per page (default 20, max 100)
#
# Example: GET /equipment?equipment_type=inverter&page=1&page_size=20
# ==============================================================================
@router.get(
    "/",
    response_model=EquipmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all equipment",
    description="Returns paginated list of stored equipment specs."
)
def list_equipment(
    equipment_type: Optional[str] = Query(
        default=None,
        description="Filter by equipment type e.g. inverter"
    ),
    equipment_sub_type: Optional[str] = Query(
        default=None,
        description="Filter by sub-type e.g. solaredge_inverter"
    ),
    manufacturer: Optional[str] = Query(
        default=None,
        description="Filter by manufacturer name"
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    from app.repositories.equipment_repository import EquipmentRepository

    repo = EquipmentRepository(db)
    items, total = repo.get_all(
        equipment_type=equipment_type,
        equipment_sub_type=equipment_sub_type,
        manufacturer=manufacturer,
        page=page,
        page_size=page_size
    )

    # Return paginated response
    return EquipmentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


# ==============================================================================
# GET /equipment/{equipment_id}
# ------------------------------------------------------------------------------
# Fetch a single equipment record by its UUID.
#
# Example: GET /equipment/3f8a12b1-4c2d-...
# ==============================================================================
@router.get(
    "/{equipment_id}",
    response_model=EquipmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get equipment by ID",
    description="Returns a single equipment record by its UUID."
)
def get_equipment_by_id(
    equipment_id: UUID,
    db: Session = Depends(get_db)
):
    from app.repositories.equipment_repository import EquipmentRepository

    repo = EquipmentRepository(db)
    equipment = repo.get_by_id(equipment_id)

    if not equipment:
        # Return 404 if equipment not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment {equipment_id} not found"
        )

    return equipment


# ==============================================================================
# DELETE /equipment/{equipment_id}
# ------------------------------------------------------------------------------
# Delete an equipment record by UUID.
# Admin use only — not part of normal extraction flow.
# ==============================================================================
@router.delete(
    "/{equipment_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete equipment",
    description="Deletes an equipment record and clears it from Redis cache."
)
def delete_equipment(
    equipment_id: UUID,
    db: Session = Depends(get_db)
):
    from app.repositories.equipment_repository import EquipmentRepository
    from app.core.redis import redis_client

    repo = EquipmentRepository(db)

    # Check it exists first
    equipment = repo.get_by_id(equipment_id)
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment {equipment_id} not found"
        )

    # Delete from Redis cache if it exists there
    if equipment.manufacturer and equipment.model:
        redis_client.delete(equipment.manufacturer, equipment.model)

    # Delete from database
    repo.delete(equipment_id)

    return {
        "status": "success",
        "message": f"Equipment {equipment_id} deleted successfully"
    }