"""
==============================================================================
scripts/seed_equipment_with_urls.py
==============================================================================
PURPOSE:
  Create sample equipment records with source URLs properly set.
  
RUN:
  python scripts/seed_equipment_with_urls.py
==============================================================================
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, create_tables
from app.models.equipment_model import Equipment, EquipmentCategory

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Equipment records with source URLs pre-configured
EQUIPMENT_TO_CREATE = [
    {
        "label": "REC Alpha Pure-R 430W",
        "category": EquipmentCategory.SOURCE,
        "equipment_type": "module",
        "equipment_sub_type": "pv_module",
        "manufacturer": "REC",
        "model": "Alpha Pure-R 430W",
        "original_source_url": "https://www.recgroup.com/en-us/modules/purity-r/rec-alpha-pure-r-430w",
        "source_url": "https://sjc1.vultrobjects.com/test1/equipment/module/rec/alpha_pure_r_430w/rec_alpha_430w.pdf",
        "equipment_metadata": {
            "imp_a": 10.42,
            "isc_a": 10.94,
            "vmp_v": 41.3,
            "voc_v": 49.61,
            "wattage_w": 430,
            "weight_kg": 21,
            "ul_listing": "UL 61730",
            "dimensions_mm": "1721 x 1134 x 30 mm",
            "max_system_voltage_v": 1000,
            "temperature_coefficient_isc": 0.04,
            "temperature_coefficient_voc": -0.24,
            "temperature_coefficient_pmax": -0.26
        },
        "confident_score": 0.95
    },
    {
        "label": "Fronius Primo 10.0-1",
        "category": EquipmentCategory.CONVERSION,
        "equipment_type": "inverter",
        "equipment_sub_type": "string_inverter",
        "manufacturer": "Fronius",
        "model": "Primo 10.0-1",
        "original_source_url": "https://www.fronius.com/en-us/solar/inverters/all-inverters/primo",
        "source_url": "https://sjc1.vultrobjects.com/test1/equipment/inverter/fronius/primo_10_0_1/fronius_primo_10.pdf",
        "equipment_metadata": {
            "phase": "1-phase",
            "wattage_w": 10000,
            "weight_kg": 21.5,
            "ul_listing": True,
            "frequency_hz": 50,
            "dimensions_mm": "725 x 510 x 225 mm",
            "mppt_channels": 2,
            "max_dc_input_w": 15000,
            "enclosure_rating": "IP65",
            "has_builtin_afci": "Not available",
            "max_dc_voltage_v": 1000,
            "cec_efficiency_pct": 96.5,
            "max_input_current_a": 27,
            "peak_efficiency_pct": 98,
            "nominal_ac_voltage_v": 220,
            "max_ac_output_current_a": 45.5,
            "has_builtin_dc_disconnect": True,
            "has_builtin_rapid_shutdown": "Not available",
            "is_rapid_shutdown_compliant": "Not available",
            "max_input_current_per_mppt_a": 18
        },
        "confident_score": 0.81
    },
    {
        "label": "Enphase IQ8M",
        "category": EquipmentCategory.CONVERSION,
        "equipment_type": "inverter",
        "equipment_sub_type": "microinverter",
        "manufacturer": "Enphase",
        "model": "IQ8M",
        "original_source_url": "https://enphase.com/en-us/products-and-services/iq-microinverter",
        "source_url": "https://sjc1.vultrobjects.com/test1/equipment/inverter/enphase/iq8m/enphase_iq8m.pdf",
        "equipment_metadata": {
            "weight_kg": 1.1,
            "ul_listing": "UL1741 SA",
            "frequency_hz": 60,
            "dimensions_mm": "242 mm x 161 mm x 48 mm",
            "enclosure_rating": "IP67",
            "max_input_power_w": 400,
            "cec_efficiency_pct": 97,
            "max_mppt_voltage_v": 48,
            "min_mppt_voltage_v": 27,
            "max_input_current_a": 11.5,
            "max_input_voltage_v": 60,
            "peak_efficiency_pct": 97.5,
            "peak_output_power_w": 330,
            "nominal_ac_voltage_v": 240,
            "branch_circuit_limits": "20 A",
            "max_ac_output_current_a": 1.37,
            "is_rapid_shutdown_compliant": True
        },
        "confident_score": 0.95
    },
    {
        "label": "SolarEdge P370",
        "category": EquipmentCategory.CONVERSION,
        "equipment_type": "optimizer",
        "equipment_sub_type": "optimizer",
        "manufacturer": "SolarEdge",
        "model": "P370",
        "original_source_url": "https://www.solaredge.com/en/products/power-optimizers/p370",
        "source_url": "https://sjc1.vultrobjects.com/test1/equipment/optimizer/solaredge/p370/solaredge_p370.pdf",
        "equipment_metadata": {
            "weight_kg": 0.5,
            "dimensions_mm": "122 x 159 x 27.5 mm",
            "certifications": "IEC62109, AS/NZS 60068.2.68, AS/NZS 60068.2.64, VDE AR N 4105, EN 50549-1, IEC62109-1, IEC62109-2, EN 61000-6-2, EN 61000-6-3, FCC Part 15 Class B, ICES-003 Class B",
            "protection_rating": "IP68",
            "mppt_max_voltage_v": 48,
            "mppt_min_voltage_v": 12.5,
            "max_input_current_a": 11.5,
            "peak_efficiency_pct": 99.5,
            "rated_input_power_w": 370,
            "max_output_current_a": 3.3,
            "max_output_voltage_v": 400,
            "max_system_voltage_v": 1000,
            "operating_temp_max_c": "+85°C",
            "operating_temp_min_c": "-40°C",
            "module_level_monitoring": True,
            "safety_output_voltage_v": 1,
            "weighted_efficiency_pct": 98.8,
            "rapid_shutdown_compliant": True,
            "absolute_max_input_voltage_v": 60
        },
        "confident_score": 0.95
    },
    {
        "label": "LG Energy Solution RESU 10H Prime",
        "category": EquipmentCategory.STORAGE,
        "equipment_type": "battery",
        "equipment_sub_type": "ess",
        "manufacturer": "LG Energy Solution",
        "model": "RESU 10H Prime",
        "original_source_url": "https://www.lg.com/us/business/battery-energy-storage-systems/lg-chem-resu",
        "source_url": "https://sjc1.vultrobjects.com/test1/equipment/battery/lg/resu_10h_prime/lg_resu_10h.pdf",
        "equipment_metadata": {
            "weight_kg": 99.8,
            "ul_listing": True,
            "peak_power_w": 7000,
            "dimensions_mm": "744 x 907 x 206",
            "enclosure_rating": "IP55",
            "nominal_voltage_v": 400,
            "total_capacity_kwh": "9.8 kWh",
            "usable_capacity_kwh": "9.3 kWh",
            "max_charge_current_a": 17,
            "depth_of_discharge_pct": 95,
            "max_continuous_power_w": 5000,
            "max_discharge_current_a": 12,
            "round_trip_efficiency_pct": 90,
            "operating_temperature_range": "-10°C to 45°C"
        },
        "confident_score": 0.95
    },
    {
        "label": "IronRidge XR10 Rail",
        "category": EquipmentCategory.CONVERSION,
        "equipment_type": "racking",
        "equipment_sub_type": "mounting_rail",
        "manufacturer": "IronRidge",
        "model": "XR10 Rail",
        "original_source_url": "https://files.ironridge.com/roofmounting/cutsheets/IronRidge_Cut_Sheet_XR10_Rail.pdf",
        "source_url": "https://sjc1.vultrobjects.com/test1/equipment/racking/ironridge/xr10_rail/20260316_130017.pdf",
        "equipment_metadata": {
            "finish": "Clear Anodized",
            "anodized": True,
            "material": "6000-Series Aluminum",
            "ul_listing": "UL 2703",
            "is_aluminum": "Not available",
            "max_span_mm": "Not available",
            "compatibility": "Works with most framed modules",
            "weight_per_rail_lb": "6.10 lbs.",
            "available_lengths_in": "168\"",
            "variant_part_numbers": "XR-10-168M, XR-10-184M",
            "max_load_per_clamp_kg": "Not available",
            "section_modulus_x_in3": "0.136 in³",
            "cross_section_area_in2": "0.363 in²",
            "cross_section_width_in": "1.75",
            "torsional_constant_in4": "0.076 in³",
            "cross_section_height_in": "1.6",
            "moment_of_inertia_x_in4": "0.124 in",
            "moment_of_inertia_y_in4": "0.032 in",
            "polar_moment_of_inertia_in4": "0.033 in"
        },
        "confident_score": 0.9
    },
]


def seed_equipment():
    """Create sample equipment with URLs."""
    
    db = SessionLocal()
    
    try:
        logger.info(f"Creating {len(EQUIPMENT_TO_CREATE)} equipment records with URLs...")
        
        created = 0
        for equip_data in EQUIPMENT_TO_CREATE:
            # Check if already exists
            existing = db.query(Equipment).filter(
                Equipment.manufacturer == equip_data["manufacturer"],
                Equipment.model == equip_data["model"]
            ).first()
            
            if existing:
                logger.info(f"  ⊘ {equip_data['manufacturer']} {equip_data['model']} (already exists)")
                continue
            
            # Create new equipment
            equipment = Equipment(**equip_data)
            db.add(equipment)
            created += 1
            logger.info(f"  ✓ {equip_data['manufacturer']} {equip_data['model']}")
        
        db.commit()
        logger.info(f"\n✓ Created {created} new equipment records")
        logger.info("✓ All equipment now has source URLs!")
        
    except Exception as e:
        logger.error(f"✗ Error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Seeding equipment with source URLs")
    logger.info("=" * 60)
    
    create_tables()
    seed_equipment()
    
    logger.info("=" * 60)
    logger.info("Done!")
    logger.info("=" * 60)
