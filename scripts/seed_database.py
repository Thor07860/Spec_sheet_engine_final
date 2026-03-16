# ==============================================================================
# scripts/seed_database.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Seeds the database with:
#   1. All equipment templates (spec fields per equipment sub-type)
#   2. All trusted source domains (US solar manufacturers)
#
# RUN THIS ONCE after first startup:
#   python -m scripts.seed_database
#
# SAFE TO RUN MULTIPLE TIMES:
#   Uses "upsert" logic — if a record already exists it skips it.
#   Will never duplicate data.
#
# AFTER RUNNING:
#   Your extraction pipeline is fully operational.
#   POST /equipment will find templates and trusted sources immediately.
# ==============================================================================

import sys
import os

# Add project root to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, create_tables
from app.models.equipment_model import EquipmentTemplate, TrustedSource

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ==============================================================================
# EQUIPMENT TEMPLATES
# ------------------------------------------------------------------------------
# Each entry defines what fields Gemini should extract for that equipment type.
# Keys with None = extract this value from the spec sheet
# Keys with a value = this is a default/known value
#
# HOW TO ADD A NEW EQUIPMENT TYPE IN THE FUTURE:
#   Add a new dict to EQUIPMENT_TEMPLATES below and re-run this script.
#   Zero code changes needed anywhere else.
# ==============================================================================
EQUIPMENT_TEMPLATES = [

    # --------------------------------------------------------------------------
    # PV Module (DC)
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "pv_module",
        "description": "Standard DC photovoltaic module",
        "schema_template": {
            "wattage_w": None,
            "voc_v": None,
            "isc_a": None,
            "vmp_v": None,
            "imp_a": None,
            "max_system_voltage_v": None,
            "temperature_coefficient_pmax": None,
            "temperature_coefficient_voc": None,
            "temperature_coefficient_isc": None,
            "dimensions_mm": {
                "length": None,
                "width": None,
                "height": None
            },
            "weight_kg": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # AC Module
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "ac_module",
        "description": "AC module with integrated microinverter",
        "schema_template": {
            "module_power_w": None,
            "ac_output_power_w": None,
            "max_output_current_a": None,
            "grid_voltage_v": None,
            "efficiency_pct": None,
            "voc_v": None,
            "isc_a": None,
            "weight_kg": None,
            "dimensions_mm": {
                "length": None,
                "width": None,
                "height": None
            },
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # SolarEdge Optimizer
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "se_optimizer",
        "description": "SolarEdge DC-DC power optimizer",
        "schema_template": {
            # "rated_input_power_w": None,
            # "max_input_voltage_v": None,
            # "max_input_current_a": None,
            # "max_output_voltage_v": None,
            # "max_output_current_a": None,
            # "efficiency_pct": None,
            # "weight_kg": None,
            # "dimensions_mm": None,
            # "ul_listing": None,
            # "manufacturer": None,
            # "model": None,
            "manufacturer": None,
            "model": None,

            "rated_input_power_w": None,
            "absolute_max_input_voltage_v": None,
            "mppt_min_voltage_v": None,
            "mppt_max_voltage_v": None,
            "max_input_current_a": None,

            "max_output_voltage_v": None,
            "max_output_current_a": None,
            "max_system_voltage_v": None,

            "peak_efficiency_pct": None,
            "weighted_efficiency_pct": None,

            "weight_kg": None,
            "dimensions_mm": {
                "length": None,
                "width": None,
                "height": None
            },

            "protection_rating": None,
            "operating_temp_min_c": None,
            "operating_temp_max_c": None,

            "safety_output_voltage_v": None,
            "rapid_shutdown_compliant": None,
            "module_level_monitoring": None,

            "certifications": [],
            "datasheet_source_type": None

        }
    },

    # --------------------------------------------------------------------------
    # MLPE (Module Level Power Electronics)
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "mlpe",
        "description": "Module Level Power Electronics",
        "schema_template": {
            "rated_input_power_w": None,
            "max_input_voltage_v": None,
            "max_input_current_a": None,
            "max_output_voltage_v": None,
            "max_output_current_a": None,
            "efficiency_pct": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # DC Disconnect (Fused)
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "fused_dc_disconnect",
        "description": "Fused DC disconnect switch",
        "schema_template": {
            "max_voltage_v": None,
            "max_current_a": None,
            "fuse_rating_a": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # DC Disconnect (Non-Fused)
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "non_fused_dc_disconnect",
        "description": "Non-fused DC disconnect switch",
        "schema_template": {
            "max_voltage_v": None,
            "max_current_a": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # DC Combiner Box
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "combiner_box",
        "description": "DC combiner box for string aggregation",
        "schema_template": {
            "max_input_voltage_v": None,
            "max_output_current_a": None,
            "number_of_inputs": None,
            "fuse_rating_a": None,
            "enclosure_rating": None,
            "has_monitoring": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Rapid Shutdown Switch
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "rsd_switch",
        "description": "Rapid shutdown switch for NEC 2017/2020 compliance",
        "schema_template": {
            "max_voltage_v": None,
            "max_current_a": None,
            "is_nec_2017_compliant": None,
            "is_nec_2020_compliant": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Surge Protection Device
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "surge_protector",
        "description": "DC or AC surge protection device",
        "schema_template": {
            "max_continuous_voltage_v": None,
            "max_discharge_current_ka": None,
            "voltage_protection_level_v": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # String Inverter
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "string_inverter",
        "description": "Standard string inverter",
        "schema_template": {
            "wattage_w": None,
            "max_dc_input_w": None,
            "max_dc_voltage_v": None,
            "max_input_current_a": None,
            "mppt_channels": None,
            "max_input_current_per_mppt_a": None,
            "nominal_ac_voltage_v": None,
            "max_ac_output_current_a": None,
            "frequency_hz": None,
            "phase": None,
            "peak_efficiency_pct": None,
            "cec_efficiency_pct": None,
            "has_builtin_dc_disconnect": None,
            "has_builtin_afci": None,
            "has_builtin_rapid_shutdown": None,
            "is_rapid_shutdown_compliant": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "weight_kg": None,
            "dimensions_mm": {
                "length": None,
                "width": None,
                "height": None
            },
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # SolarEdge Inverter
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "solaredge_inverter",
        "description": "SolarEdge HD-Wave or similar inverter with optimizer support",
        "schema_template": {
            "manufacturer": None,
            "model": None,
            "nominal_ac_power_output_w": None,
            "ac_output_voltage_v": None,
            "max_continuous_output_current_a": None,
            "maximum_dc_power_stc_w": None,
            "max_input_voltage_v": None,
            "nominal_dc_input_voltage_v": None,
            "max_input_current_a": None,
            "maximum_inverter_efficiency_pct": None,
            "cec_weighted_efficiency_pct": None,
            "dc_input_conduit_size_strings_awg": None,
            "cooling_method": None,
            "operating_temp_min_c": None,
            "operating_temp_max_c": None,
            "ul_listing": None,
            "weight_kg": None,
            "dimensions_mm": {
                "length": None,
                "width": None,
                "height": None
            }
        }
    },

    # --------------------------------------------------------------------------
    # Microinverter
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "microinverter",
        "description": "Module-level microinverter",
        "schema_template": {
            "max_input_power_w": None,
            "peak_output_power_w": None,
            "max_input_voltage_v": None,
            "min_mppt_voltage_v": None,
            "max_mppt_voltage_v": None,
            "max_input_current_a": None,
            "nominal_ac_voltage_v": None,
            "max_ac_output_current_a": None,
            "frequency_hz": None,
            "peak_efficiency_pct": None,
            "cec_efficiency_pct": None,
            "is_rapid_shutdown_compliant": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "weight_kg": None,
            "dimensions_mm": {
                "length": None,
                "width": None,
                "height": None
            },
            "branch_circuit_limits": [
                {
                    "breaker_rating_a": None, 
                    "voltage_type": None,
                    "max_units": None
                }

            ],
            "manufacturer": None,
            "model": None,
            

        }
    },

    # --------------------------------------------------------------------------
    # Junction Box
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "junction_box",
        "description": "AC junction box — converts manufacturer cable to AWG",
        "schema_template": {
            "max_voltage_v": None,
            "max_current_a": None,
            "enclosure_rating": None,
            "wire_gauge_awg": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Load Center
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "load_center",
        "description": "AC load center / IQ Combiner with built-in gateway",
        "schema_template": {
            "max_ac_voltage_v": None,
            "max_current_a": None,
            "number_of_circuits": None,
            "has_builtin_gateway": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Envoy / Monitoring Gateway
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "envoy",
        "description": "Enphase Envoy or similar monitoring gateway",
        "schema_template": {
            "communication_interfaces": None,
            "max_microinverters_supported": None,
            "monitoring_features": None,
            "requires_subscription": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Consumption CT
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "consumption_ct",
        "description": "Current transformer for consumption monitoring",
        "schema_template": {
            "max_current_a": None,
            "accuracy_pct": None,
            "wire_gauge_compatibility": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # AC Disconnect (Fused)
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "fused_ac_disconnect",
        "description": "Fused AC disconnect switch",
        "schema_template": {
            "max_voltage_v": None,
            "max_current_a": None,
            "fuse_rating_a": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # AC Disconnect (Non-Fused)
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "non_fused_ac_disconnect",
        "description": "Non-fused AC disconnect switch",
        "schema_template": {
            "max_voltage_v": None,
            "max_current_a": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Battery / ESS (Energy Storage System)
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "ess",
        "description": "Battery energy storage system",
        "schema_template": {
            "usable_capacity_kwh": None,
            "total_capacity_kwh": None,
            "max_continuous_power_w": None,
            "peak_power_w": None,
            "nominal_voltage_v": None,
            "max_charge_current_a": None,
            "max_discharge_current_a": None,
            "round_trip_efficiency_pct": None,
            "depth_of_discharge_pct": None,
            "operating_temperature_range": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "weight_kg": None,
            "dimensions_mm": {
                "length": None,
                "width": None,
                "height": None
            },
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Backup Gateway
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "backup_gateway",
        "description": "Gateway for backup power management",
        "schema_template": {
            "max_continuous_power_w": None,
            "transfer_time_ms": None,
            "ac_input_voltage_v": None,
            "ac_output_voltage_v": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Backup Load Panel
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "backup_load_panel",
        "description": "Sub-panel for backup loads",
        "schema_template": {
            "max_voltage_v": None,
            "max_current_a": None,
            "number_of_circuits": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Transfer Switch (ATS)
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "transfer_switch",
        "description": "Automatic transfer switch",
        "schema_template": {
            "max_voltage_v": None,
            "max_current_a": None,
            "transfer_time_ms": None,
            "is_automatic": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Production Meter
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "production_meter",
        "description": "Solar production revenue grade meter",
        "schema_template": {
            "max_voltage_v": None,
            "max_current_a": None,
            "accuracy_class": None,
            "communication_interface": None,
            "is_revenue_grade": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Utility Meter
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "utility_meter",
        "description": "Utility interconnection meter",
        "schema_template": {
            "max_voltage_v": None,
            "max_current_a": None,
            "meter_type": None,
            "communication_interface": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Main Service Panel (MSP)
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "main_service_panel",
        "description": "Main electrical service panel",
        "schema_template": {
            "main_breaker_rating_a": None,
            "bus_rating_a": None,
            "number_of_spaces": None,
            "max_voltage_v": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------
    # Charge Controller (MPPT/PWM)
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "charge_controller",
        "description": "DC-DC charge controller for battery systems (MPPT or PWM)",
        "schema_template": {
            "max_input_voltage_v": None,
            "max_input_current_a": None,
            "max_output_current_a": None,
            "battery_voltage_nominal_v": None,
            "max_power_w": None,
            "controller_type": None,  # MPPT or PWM
            "efficiency_pct": None,
            "temperature_compensation": None,
            "remote_monitoring_capable": None,
            "enclosure_rating": None,
            "ul_listing": None,
            "weight_kg": None,
            "dimensions_mm": {
                "length": None,
                "width": None,
                "height": None
            },
            "manufacturer": None,
            "model": None,
        }
    },

    # --------------------------------------------------------------------------
    # Mounting Rails / Racking System
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "mounting_rail",
        "description": "PV module mounting rail / racking system",
        "schema_template": {
            "manufacturer": None,
            "model": None,
            "material": None,
            "finish": None,                      # mill / black / anodized / bare
            "is_aluminum": None,
            "compatibility": None,

            "cross_section_height_in": None,
            "cross_section_width_in": None,
            "cross_section_area_in2": None,

            "section_modulus_x_in3": None,
            "moment_of_inertia_x_in4": None,
            "moment_of_inertia_y_in4": None,
            "torsional_constant_in4": None,
            "polar_moment_of_inertia_in4": None,

            "available_lengths_in": None,        # list
            "weight_per_rail_lb": None,          # list or variant-based
            "variant_part_numbers": None,        # list/dict

            "max_span_mm": None,
            "max_load_per_clamp_kg": None,

            "ul_listing": None,
            "anodized": None
          
        }
    },

    # --------------------------------------------------------------------------
    # Utility Grid
    # --------------------------------------------------------------------------
    {
        "equipment_sub_type": "utility_grid",
        "description": "Utility grid connection point",
        "schema_template": {
            "grid_voltage_v": None,
            "frequency_hz": None,
            "phase": None,
            "utility_name": None,
        }
    },
]


# ==============================================================================
# TRUSTED SOURCES
# ------------------------------------------------------------------------------
# US solar equipment manufacturers and trusted datasheet repositories.
# trust_score: 100 = official manufacturer, 40 = third-party repository
# ==============================================================================
TRUSTED_SOURCES = [

    # --- Tier 1: Official Manufacturers (trust_score = 100) ---
   
    {"domain": "knowledge-center.solaredge.com", "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "solaredge.com",         "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "enphase.com",           "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "tesla.com", "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "energylibrary.tesla.com", "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "siemens.com", "trust_score": 100, "source_type": "manufacturer"},
   
    {"domain": "fronius.com",           "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "sma-america.com",       "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "sma.de",                "trust_score": 95,  "source_type": "manufacturer"},
    {"domain": "generac.com",           "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "panasonic.com",         "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "qcells.com",            "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "recgroup.com",          "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "canadiansolar.com",     "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "trinasolar.com",        "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "jinkosolar.com",        "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "longi-solar.com",       "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "longi.com",             "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "sunpower.com",          "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "apsystems.com",         "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "tigoenergy.com",        "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "hoymiles.com",          "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "schneider-electric.com","trust_score": 100, "source_type": "manufacturer"},
    {"domain": "midniteolar.com",       "trust_score": 95,  "source_type": "manufacturer"},
    {"domain": "outbackpower.com",      "trust_score": 95,  "source_type": "manufacturer"},
    {"domain": "chintpower.com",        "trust_score": 90,  "source_type": "manufacturer"},
    {"domain": "ablenergy.com",         "trust_score": 90,  "source_type": "manufacturer"},
    {"domain": "siemens.com",           "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "eaton.com",             "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "square-d.com",          "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "lgeneralelectric.com",  "trust_score": 100, "source_type": "manufacturer"},
    {"domain": "aeroenv.com",           "trust_score": 90,  "source_type": "manufacturer"},
    {"domain": "itek-energy.com",       "trust_score": 90,  "source_type": "manufacturer"},

    # --- Tier 2: Trusted Distributors (trust_score = 75) ---
    {"domain": "altestore.com",         "trust_score": 75,  "source_type": "distributor"},
    {"domain": "wholesalesolar.com",    "trust_score": 75,  "source_type": "distributor"},
    {"domain": "solar-electric.com",    "trust_score": 75,  "source_type": "distributor"},
    {"domain": "sunelec.com",           "trust_score": 75,  "source_type": "distributor"},

    # --- Tier 3: Datasheet Repositories (trust_score = 50) ---
    {"domain": "manualslib.com",        "trust_score": 50,  "source_type": "repository"},
    {"domain": "datasheets.com",        "trust_score": 50,  "source_type": "repository"},
    {"domain": "solarreviews.com",      "trust_score": 50,  "source_type": "repository"},
    {"domain": "energysage.com",        "trust_score": 55,  "source_type": "repository"},
    {"domain": "gogreensolar.com",      "trust_score": 50,  "source_type": "repository"},
]


# ==============================================================================
# SEEDER FUNCTIONS
# ==============================================================================

def seed_templates(db):
    """Insert equipment templates — skip if already exists."""

    logger.info("Seeding equipment templates...")
    inserted = 0
    skipped = 0

    for template_data in EQUIPMENT_TEMPLATES:

        # Check if template already exists
        existing = (
            db.query(EquipmentTemplate)
            .filter(
                EquipmentTemplate.equipment_sub_type == template_data["equipment_sub_type"]
            )
            .first()
        )

        if existing:
            # Already exists — skip
            skipped += 1
            continue

        # Insert new template
        template = EquipmentTemplate(
            equipment_sub_type=template_data["equipment_sub_type"],
            description=template_data["description"],
            schema_template=template_data["schema_template"],
            is_active=True
        )
        db.add(template)
        inserted += 1

    db.commit()
    logger.info(
        "Templates: %d inserted, %d already existed (skipped)",
        inserted, skipped
    )


def seed_trusted_sources(db):
    """Insert trusted source domains — skip if already exists."""

    logger.info("Seeding trusted sources...")
    inserted = 0
    skipped = 0

    for source_data in TRUSTED_SOURCES:

        # Check if domain already exists
        existing = (
            db.query(TrustedSource)
            .filter(TrustedSource.domain == source_data["domain"])
            .first()
        )

        if existing:
            skipped += 1
            continue

        # Insert new trusted source
        source = TrustedSource(
            domain=source_data["domain"],
            trust_score=source_data["trust_score"],
            country="US",
            source_type=source_data["source_type"],
            is_active=True
        )
        db.add(source)
        inserted += 1

    db.commit()
    logger.info(
        "Trusted sources: %d inserted, %d already existed (skipped)",
        inserted, skipped
    )


def run():
    """Main seeder entry point."""

    logger.info("=" * 60)
    logger.info("Starting database seeder")
    logger.info("=" * 60)

    # Ensure all tables exist first
    logger.info("Creating tables if not exist...")
    create_tables()

    # Open database session
    db = SessionLocal()

    try:
        seed_templates(db)
        seed_trusted_sources(db)

        logger.info("=" * 60)
        logger.info("Database seeding complete!")
        logger.info("Your extraction pipeline is ready.")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("Seeding failed: %s", str(e))
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    run()