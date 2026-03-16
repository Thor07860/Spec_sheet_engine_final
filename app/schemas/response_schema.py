# ==============================================================================
# schemas/response_schema.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Contains ONLY outgoing response schemas — what the API sends BACK.
#   Every schema here represents data flowing OUT to PMS, calculation engine,
#   or SLD generator.
#
# RULE: Nothing in this file should define what the API receives.
#       That belongs in request_schema.py.
# ==============================================================================

from pydantic import BaseModel, Field, field_validator, SkipValidation
from typing import Optional, Any, List
from datetime import datetime
from uuid import UUID

# Import enums from the model layer — single source of truth
from app.models.equipment_model import EquipmentCategory, MatchType


# ==============================================================================
# SourceDocument
# ==============================================================================
# Groups source information together for cleaner response structure
# ==============================================================================
class SourceDocument(BaseModel):
    original_url: Optional[str] = None
    processed_url: Optional[str] = None

    class Config:
        from_attributes = True


# ==============================================================================
# Confidence
# ==============================================================================
# Groups confidence information separately
# ==============================================================================
class Confidence(BaseModel):
    score: Optional[float] = None

    class Config:
        from_attributes = True


# ==============================================================================
# EquipmentData
# ==============================================================================
# Clean PMS-facing equipment data structure with:
# - No internal fields (priority, timestamps, job_id)
# - Specifications grouped separately (no duplicated identity fields)
# - Source info grouped together
# - Confidence grouped separately
#
# This is the NEW preferred response structure for all API responses.
# ==============================================================================
class EquipmentData(BaseModel):
    id: UUID
    label: str
    category: EquipmentCategory
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    equipment_type: str
    equipment_sub_type: str

    # Extracted specifications — JSONB, different structure per equipment type
    # Only contains actual specs, no duplicated identity fields
    specifications: Optional[SkipValidation[dict[str, Any]]] = Field(default=None)

    # Grouped source information
    source_document: Optional[SourceDocument] = None
    
    # Grouped confidence information
    confidence: Optional[Confidence] = None

    class Config:
        from_attributes = True


# ==============================================================================
# EquipmentResponse
# ------------------------------------------------------------------------------
# The full equipment record returned to PMS after extraction.
# This is the primary data structure the calculation engine consumes.
#
# HOW TO ADD A NEW FIELD IN THE FUTURE:
#   1. Add the field to the Equipment SQLAlchemy model (equipment_model.py)
#   2. Add the field here in EquipmentResponse
#   3. Run create_tables() — it won't drop existing data
#   That's it. No other files need to change.
#
# Example response:
# {
#     "id": "3f8a12b1-...",
#     "label": "SolarEdge SE7600H-US",
#     "category": "conversion",
#     "equipment_type": "inverter",
#     "equipment_sub_type": "solaredge_inverter",
#     "manufacturer": "SolarEdge",
#     "model": "SE7600H-US",
#     "priority": 31,
#     "metadata": { "wattage_w": 7600, "max_dc_voltage_v": 480 },
#     "original_source_url": "https://solaredge.com/content/dam/solaredge/en_US/documents/datasheets/se7600h-us-datasheet.pdf",
#     "source_url": "https://sjc1.vultrobjects.com/test1/equipment/inverter/solaredge/se7600h-us/20260316_082029.pdf",
#     "confidence_score": 0.94,
#     "created_at": "2024-01-15T10:30:00Z"
# }
# ==============================================================================
class EquipmentResponse(BaseModel):

    id: UUID
    label: str
    category: EquipmentCategory
    equipment_type: str
    equipment_sub_type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    priority: int

    # The extracted specs — JSONB, different structure per equipment type
    # Optional because extraction might be partial
    metadata: Optional[SkipValidation[dict[str, Any]]] = Field(default=None, alias="equipment_metadata")

    # Original source URL (where the spec sheet was found)
    original_source_url: Optional[str] = None
    
    # Current source URL (may be S3 cached version)
    source_url: Optional[str] = None
    
    # Map from model's confident_score to API's confidence_score using Field alias
    confidence_score: Optional[float] = Field(default=None, alias="confident_score")
    created_at: datetime
    updated_at: datetime

    class Config:
        # Allows Pydantic to read directly from SQLAlchemy model instances
        # Without this you'd have to manually convert: Equipment.__dict__
        from_attributes = True
        # Allow populating from both field name and alias
        populate_by_name = True


# ==============================================================================
# EquipmentSearchResponse
# ------------------------------------------------------------------------------
# Returned when searching equipment by manufacturer + model.
# Includes match metadata so the caller knows if it's exact or approximate.
#
# WHY THIS MATTERS FOR THE CALCULATION ENGINE:
#   If match_type = "approximate", the engine knows to treat results
#   with slightly lower confidence — it may be a similar but not identical model.
# ==============================================================================
class EquipmentSearchResponse(BaseModel):

    # exact | approximate | not_found
    match_type: MatchType

    # The model we actually matched to (may differ from what was requested)
    matched_model: Optional[str] = None

    # Fuzzy similarity percentage — only present for approximate matches
    # Example: 94.5 means 94.5% similar to the requested model
    similarity_score: Optional[float] = None

    # Full equipment data — None if not_found
    data: Optional[EquipmentResponse] = None

    # Human readable message explaining what happened
    message: str


# ==============================================================================
# EquipmentListResponse
# ------------------------------------------------------------------------------
# Paginated list of equipment.
# Used by GET /equipment for browsing all stored equipment.
# ==============================================================================
class EquipmentListResponse(BaseModel):

    # Total records in the database matching the filter
    total: int

    # Current page number
    page: int

    # Records per page
    page_size: int

    # The equipment records for this page
    items: List[EquipmentResponse]


# ==============================================================================
# TrustedSourceResponse
# ------------------------------------------------------------------------------
# Response shape for trusted source records.
# Used when listing or adding trusted domains.
# ==============================================================================
class TrustedSourceResponse(BaseModel):

    id: int
    domain: str
    trust_score: int
    country: str
    source_type: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==============================================================================
# TemplateResponse
# ------------------------------------------------------------------------------
# Response shape for equipment spec templates.
# Shows what fields are defined for a given equipment sub-type.
#
# HOW TO ADD A NEW EQUIPMENT TYPE IN THE FUTURE:
#   POST /templates with:
#   {
#     "equipment_sub_type": "ev_charger",
#     "schema_template": {
#       "max_power_kw": null,
#       "voltage_v": null,
#       "connector_type": null
#     }
#   }
#   The extraction pipeline picks it up automatically — no code change needed.
# ==============================================================================
class TemplateResponse(BaseModel):

    id: int
    equipment_sub_type: str

    # The full JSON schema defining what fields to extract
    schema_template: SkipValidation[dict[str, Any]]

    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True