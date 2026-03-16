# ==============================================================================
# schemas/request_schema.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Contains ONLY incoming request schemas — what the API expects to RECEIVE.
#   Every schema here represents a request body from PMS or admin.
#
# RULE: Nothing in this file should define what goes OUT of the API.
#       That belongs in response_schema.py.
# ==============================================================================

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List


# ==============================================================================
# EquipmentRequest
# ------------------------------------------------------------------------------
# The main request body PMS sends when it wants equipment specs extracted.
#
# Example incoming JSON:
# {
#     "manufacturer": "SolarEdge",
#     "model": "SE7600H-US",
#     "equipment_type": "inverter",
#     "equipment_sub_type": "solaredge_inverter"
# }
# ==============================================================================
class EquipmentRequest(BaseModel):

    # Manufacturer name — required, must not be empty
    manufacturer: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Equipment manufacturer name",
        examples=["SolarEdge", "Enphase", "Fronius"]
    )

    # Model name — required, must not be empty
    model: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Equipment model name",
        examples=["SE7600H-US", "IQ8Plus", "Primo 5.0"]
    )

    # Broad equipment type — required
    equipment_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Broad equipment type e.g. inverter, module, optimizer"
    )

    # Specific sub-type — must match a template defined in EquipmentTemplate table
    equipment_sub_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Equipment sub-type matching a defined extraction template"
    )

    # --------------------------------------------------------------------------
    # VALIDATORS
    # These run before any service or route code touches the data.
    # --------------------------------------------------------------------------

    @field_validator("manufacturer", "model", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        """Strip leading/trailing whitespace. Prevents ' SolarEdge ' mismatches."""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("equipment_type", "equipment_sub_type", mode="before")
    @classmethod
    def normalize_lowercase(cls, value: str) -> str:
        """
        Normalize to lowercase. 
        'Inverter' and 'inverter' must map to the same template.
        """
        if isinstance(value, str):
            return value.strip().lower()
        return value

    class Config:
        json_schema_extra = {
            "example": {
                "manufacturer": "SolarEdge",
                "model": "SE7600H-US",
                "equipment_type": "inverter",
                "equipment_sub_type": "solaredge_inverter"
            }
        }


# ==============================================================================
# EquipmentBatchRequest
# ------------------------------------------------------------------------------
# Batch request for extracting specs from multiple equipment items.
# Useful for projects with multiple equipment pieces.
#
# Example incoming JSON:
# {
#     "equipments": [
#         {
#             "manufacturer": "Tesla",
#             "model": "Tesla Solar Inverter 7.6 kW",
#             "equipment_type": "inverter",
#             "equipment_sub_type": "string_inverter"
#         },
#         {
#             "manufacturer": "Enphase",
#             "model": "IQ8Plus",
#             "equipment_type": "inverter",
#             "equipment_sub_type": "microinverter"
#         },
#         {
#             "manufacturer": "SolarEdge",
#             "model": "P505",
#             "equipment_type": "optimizer",
#             "equipment_sub_type": "se_optimizer"
#         }
#     ]
# }
# ==============================================================================
class EquipmentBatchRequest(BaseModel):

    # List of equipment items to process
    equipments: List[EquipmentRequest] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of equipment items to extract specs for (1-100 items)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "equipments": [
                    {
                        "manufacturer": "Tesla",
                        "model": "Tesla Solar Inverter 7.6 kW",
                        "equipment_type": "inverter",
                        "equipment_sub_type": "string_inverter"
                    },
                    {
                        "manufacturer": "Enphase",
                        "model": "IQ8Plus",
                        "equipment_type": "inverter",
                        "equipment_sub_type": "microinverter"
                    }
                ]
            }
        }


# ==============================================================================
# TrustedSourceCreate
# ------------------------------------------------------------------------------
# Request body for adding a new trusted domain.
# Used by admin endpoints to expand the trusted sources list.
#
# Example:
# {
#     "domain": "apsystems.com",
#     "trust_score": 90,
#     "country": "US",
#     "source_type": "manufacturer"
# }
# ==============================================================================
class TrustedSourceCreate(BaseModel):

    domain: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Domain name without protocol e.g. solaredge.com"
    )

    # 0 = blacklisted, 100 = fully trusted manufacturer
    trust_score: int = Field(
        default=100,
        ge=0,
        le=100,
        description="Trust score 0-100"
    )

    country: str = Field(
        default="US",
        max_length=10
    )

    source_type: Optional[str] = Field(
        default="manufacturer",
        max_length=50,
        description="manufacturer | distributor | repository | marketplace"
    )

    @field_validator("domain", mode="before")
    @classmethod
    def clean_domain(cls, value: str) -> str:
        """
        Strip protocol and trailing slashes.
        Converts 'https://solaredge.com/' → 'solaredge.com'
        WHY: Prevents duplicate entries for the same domain in different formats.
        """
        if isinstance(value, str):
            value = value.replace("https://", "").replace("http://", "")
            value = value.rstrip("/").strip().lower()
        return value


# ==============================================================================
# EquipmentListRequest
# ------------------------------------------------------------------------------
# Query parameters for listing/filtering equipment.
# Used by GET /equipment endpoint.
#
# Example query: GET /equipment?equipment_type=inverter&page=1&page_size=20
# ==============================================================================
class EquipmentListRequest(BaseModel):

    # Optional filters — all are None by default (no filter applied)
    equipment_type: Optional[str] = Field(
        default=None,
        description="Filter by equipment type e.g. inverter"
    )

    equipment_sub_type: Optional[str] = Field(
        default=None,
        description="Filter by sub-type e.g. solaredge_inverter"
    )

    manufacturer: Optional[str] = Field(
        default=None,
        description="Filter by manufacturer name"
    )

    # Pagination — default page 1, 20 items per page
    page: int = Field(default=1, ge=1, description="Page number starting from 1")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page max 100")