# ==============================================================================
# repositories/equipment_repository.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   CRUD operations for the Equipment table ONLY.
#   This is the main table — stores final validated equipment specs.
#   Every other part of the system reads from here.
#
# RULE: This file only touches the Equipment table.
#       Nothing else. No jobs, no logs, no sources.
# ==============================================================================

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List
from uuid import UUID

from app.models.equipment_model import Equipment

import logging
logger = logging.getLogger(__name__)


class EquipmentRepository:

    def __init__(self, db: Session):
        # Inject the database session from outside
        # WHY: This class never opens its own connection.
        #      FastAPI's get_db() controls the session lifecycle.
        self.db = db

    # --------------------------------------------------------------------------
    # get_by_manufacturer_model()
    # --------------------------------------------------------------------------
    # Primary cache check — called before running Serper or Gemini.
    # If data exists here, we return it instantly without any API calls.
    #
    # Uses ilike for case-insensitive matching:
    #   "SolarEdge" == "solaredge" == "SOLAREDGE"
    # --------------------------------------------------------------------------
    def get_by_manufacturer_model(
        self,
        manufacturer: str,
        model: str
    ) -> Optional[Equipment]:

        logger.debug("DB lookup: manufacturer=%s model=%s", manufacturer, model)

        return (
            self.db.query(Equipment)
            .filter(
                and_(
                    Equipment.manufacturer.ilike(f"%{manufacturer}%"),
                    Equipment.model.ilike(f"%{model}%")
                )
            )
            .first()
        )

    # --------------------------------------------------------------------------
    # get_by_id()
    # --------------------------------------------------------------------------
    # Fetch a single equipment record by UUID.
    # Used when the caller already knows the equipment ID.
    # --------------------------------------------------------------------------
    def get_by_id(self, equipment_id: UUID) -> Optional[Equipment]:

        return (
            self.db.query(Equipment)
            .filter(Equipment.id == equipment_id)
            .first()
        )

    # --------------------------------------------------------------------------
    # get_all()
    # --------------------------------------------------------------------------
    # Paginated list with optional filters.
    #
    # Returns a tuple: (list of equipment, total count)
    # WHY TUPLE: Caller needs both the items AND total for pagination headers.
    # --------------------------------------------------------------------------
    def get_all(
        self,
        equipment_type: Optional[str] = None,
        equipment_sub_type: Optional[str] = None,
        manufacturer: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[Equipment], int]:

        query = self.db.query(Equipment)

        # Apply filters only when values are provided
        if equipment_type:
            query = query.filter(
                Equipment.equipment_type.ilike(f"%{equipment_type}%")
            )

        if equipment_sub_type:
            query = query.filter(
                Equipment.equipment_sub_type.ilike(f"%{equipment_sub_type}%")
            )

        if manufacturer:
            query = query.filter(
                Equipment.manufacturer.ilike(f"%{manufacturer}%")
            )

        # Count BEFORE pagination — gives total matching records across all pages
        total = query.count()

        # page=2, page_size=20 → skip first 20, return next 20
        offset = (page - 1) * page_size

        items = (
            query
            .order_by(Equipment.created_at.desc())  # newest first
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return items, total

    # --------------------------------------------------------------------------
    # create()
    # --------------------------------------------------------------------------
    # Insert a new equipment record after successful extraction + validation.
    #
    # WHY refresh() after commit:
    #   PostgreSQL sets created_at, updated_at server-side.
    #   Python object doesn't have those values until we refresh.
    # --------------------------------------------------------------------------
    def create(self, data: dict) -> Equipment:

        logger.info(
            "Creating equipment: %s %s",
            data.get("manufacturer"), data.get("model")
        )

        equipment = Equipment(**data)
        self.db.add(equipment)
        self.db.commit()
        self.db.refresh(equipment)

        return equipment

    def update_extracted(self, equipment_id: UUID, data: dict) -> Optional[Equipment]:
        """Update full equipment record after a forced refresh extraction."""
        equipment = self.get_by_id(equipment_id)

        if not equipment:
            logger.warning("Equipment %s not found for full refresh", equipment_id)
            return None

        equipment.label = data.get("label", equipment.label)
        equipment.category = data.get("category", equipment.category)
        equipment.equipment_type = data.get("equipment_type", equipment.equipment_type)
        equipment.equipment_sub_type = data.get("equipment_sub_type", equipment.equipment_sub_type)
        equipment.manufacturer = data.get("manufacturer", equipment.manufacturer)
        equipment.model = data.get("model", equipment.model)
        equipment.priority = data.get("priority", equipment.priority)
        equipment.equipment_metadata = data.get("equipment_metadata", equipment.equipment_metadata)
        equipment.source_url = data.get("source_url", equipment.source_url)
        equipment.confident_score = data.get("confident_score", equipment.confident_score)

        self.db.commit()
        self.db.refresh(equipment)

        logger.info("Refreshed equipment %s with new extraction", equipment_id)
        return equipment

    # --------------------------------------------------------------------------
    # update_metadata()
    # --------------------------------------------------------------------------
    # Update specs for existing equipment — used when a new spec sheet is found.
    # updated_at is set automatically by SQLAlchemy onupdate=func.now()
    # --------------------------------------------------------------------------
    def update_metadata(
        self,
        equipment_id: UUID,
        metadata: dict,
        source_url: Optional[str] = None,
        confidence_score: Optional[float] = None
    ) -> Optional[Equipment]:

        equipment = self.get_by_id(equipment_id)

        if not equipment:
            logger.warning("Equipment %s not found for update", equipment_id)
            return None

        equipment.equipment_metadata = metadata

        if source_url:
            equipment.source_url = source_url

        if confidence_score is not None:
            equipment.confident_score = confidence_score

        self.db.commit()
        self.db.refresh(equipment)

        logger.info("Updated metadata for equipment %s", equipment_id)
        return equipment

    # --------------------------------------------------------------------------
    # delete()
    # --------------------------------------------------------------------------
    # Hard delete — admin cleanup only, not part of extraction flow.
    # --------------------------------------------------------------------------
    def delete(self, equipment_id: UUID) -> bool:

        equipment = self.get_by_id(equipment_id)

        if not equipment:
            return False

        self.db.delete(equipment)
        self.db.commit()

        logger.info("Deleted equipment %s", equipment_id)
        return True