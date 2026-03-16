# ==============================================================================
# repositories/template_repository.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   CRUD operations for the EquipmentTemplate table ONLY.
#   Templates define what spec fields to extract per equipment sub-type.
#   The Gemini prompt is built from these templates.
#
# RULE: This file only touches the EquipmentTemplate table.
#
# HOW TO ADD A NEW EQUIPMENT TYPE IN THE FUTURE (zero code change):
#   POST /templates  with body:
#   {
#     "equipment_sub_type": "ev_charger",
#     "schema_template": {
#       "max_power_kw": null,
#       "connector_type": null,
#       "voltage_v": null
#     }
#   }
#   The extraction pipeline automatically supports it from that point on.
# ==============================================================================

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List

from app.models.equipment_model import EquipmentTemplate

import logging
logger = logging.getLogger(__name__)


class TemplateRepository:

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------------------------------
    # get_by_sub_type()
    # --------------------------------------------------------------------------
    # Fetch the spec template for a given equipment sub-type.
    # Called BEFORE Gemini extraction to build the extraction prompt.
    #
    # Example: sub_type="solaredge_inverter"
    # Returns template with: { "wattage_w": null, "mppt_channels": null, ... }
    # The LLM fills in those null values from the spec sheet.
    # --------------------------------------------------------------------------
    def get_by_sub_type(
        self,
        equipment_sub_type: str
    ) -> Optional[EquipmentTemplate]:

        return (
            self.db.query(EquipmentTemplate)
            .filter(
                and_(
                    EquipmentTemplate.equipment_sub_type == equipment_sub_type,
                    EquipmentTemplate.is_active == True
                )
            )
            .first()
        )

    # --------------------------------------------------------------------------
    # get_all()
    # --------------------------------------------------------------------------
    # Fetch all active templates.
    # Used by admin to see which equipment types are currently supported.
    # --------------------------------------------------------------------------
    def get_all(self) -> List[EquipmentTemplate]:

        return (
            self.db.query(EquipmentTemplate)
            .filter(EquipmentTemplate.is_active == True)
            .order_by(EquipmentTemplate.equipment_sub_type)
            .all()
        )

    # --------------------------------------------------------------------------
    # create()
    # --------------------------------------------------------------------------
    # Insert a new equipment template.
    # This is how you add support for new equipment types without code changes.
    # --------------------------------------------------------------------------
    def create(self, data: dict) -> EquipmentTemplate:

        template = EquipmentTemplate(**data)
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)

        logger.info(
            "Created template for: %s", data.get("equipment_sub_type")
        )
        return template

    # --------------------------------------------------------------------------
    # update_schema()
    # --------------------------------------------------------------------------
    # Update the schema_template JSONB for an existing template.
    #
    # WHEN TO USE:
    #   When a new spec field needs to be extracted for an existing equipment type.
    #   Example: Add "weight_kg" to "pv_module" template.
    #   Just update the JSONB — no code change, no redeploy.
    # --------------------------------------------------------------------------
    def update_schema(
        self,
        equipment_sub_type: str,
        new_schema: dict
    ) -> Optional[EquipmentTemplate]:

        template = self.get_by_sub_type(equipment_sub_type)

        if not template:
            logger.warning(
                "Template not found for sub-type: %s", equipment_sub_type
            )
            return None

        template.schema_template = new_schema
        self.db.commit()
        self.db.refresh(template)

        logger.info("Updated schema for template: %s", equipment_sub_type)
        return template