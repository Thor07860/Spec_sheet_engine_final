# ==============================================================================
# app/services/validation/range_validators.py
# ==============================================================================
# Validates equipment specs against realistic industry ranges
# Used in PASS 2 reverification and PASS 4 cross-validation
# ==============================================================================

import logging

logger = logging.getLogger(__name__)


class RangeValidator:
    """Validates equipment specs against realistic ranges"""
    
    # PV Module ranges
    PV_MODULE_SPECS = {
        "wattage_w": (250, 750),  # Watts
        "voc_v": (30, 65),  # Open circuit voltage
        "vmp_v": (25, 50),  # Max power point voltage
        "isc_a": (8, 16),  # Short circuit current
        "imp_a": (7, 15),  # Max power current
        "weight_kg": (15, 50),  # Weight in kg
        "max_system_voltage_v": (600, 1500),  # System voltage
        "temperature_coefficient_pmax": (-0.5, -0.2)  # Temp coeff
    }
    
    # String Inverter ranges
    STRING_INVERTER_SPECS = {
        "wattage_w": (1000, 200000),  # 1kW to 200kW
        "max_dc_input_w": (1500, 300000),  # Max DC input
        "max_dc_voltage_v": (400, 1100),  # DC voltage
        "max_input_current_a": (5, 300),  # Input current
        "cec_efficiency_pct": (95, 99.5),  # Efficiency %
        "peak_efficiency_pct": (95, 99.8),
        "mppt_channels": (1, 16),  # MPPT trackers
        "max_ac_output_current_a": (10, 500),
        "nominal_ac_voltage_v": (200, 480)
    }
    
    # Microinverter ranges
    MICROINVERTER_SPECS = {
        "max_input_power_w": (300, 600),  # Input watts
        "peak_output_power_w": (240, 480),  # Output watts
        "max_input_voltage_v": (40, 80),  # DC voltage
        "max_input_current_a": (8, 20),  # Input current
        "cec_efficiency_pct": (94, 98),  # Efficiency
        "peak_efficiency_pct": (94.5, 98.5),
        "max_ac_output_current_a": (1, 3)  # AC current
    }
    
    # Battery/ESS ranges
    BATTERY_SPECS = {
        "total_capacity_kwh": (2, 30),  # Total capacity
        "usable_capacity_kwh": (1.5, 25),  # Usable capacity
        "peak_power_w": (2000, 20000),  # Peak power
        "max_continuous_power_w": (1000, 15000),  # Continuous
        "max_charge_current_a": (10, 200),  # Charge current
        "max_discharge_current_a": (10, 200),  # Discharge current
        "round_trip_efficiency_pct": (80, 98),  # Round trip efficiency
        "depth_of_discharge_pct": (80, 100),  # DoD %
        "nominal_voltage_v": (48, 400)  # Nominal voltage
    }
    
    # Surge Protector ranges
    SURGE_PROTECTOR_SPECS = {
        "max_continuous_voltage_v": (300, 1500),  # Continuous voltage
        "max_discharge_current_ka": (10, 100),  # Peak current kA
        "voltage_protection_level_v": (600, 2000)  # Protection level
    }
    
    # Combiner Box ranges
    COMBINER_BOX_SPECS = {
        "number_of_inputs": (4, 12),  # Input count
        "fuse_rating_a": (100, 600),  # Fuse rating
        "max_input_voltage_v": (400, 1100),  # Max voltage
        "max_output_current_a": (100, 600)  # Max current
    }

    @staticmethod
    def validate_pv_module(data: dict) -> tuple[bool, str]:
        """Validate PV module specs"""
        for field, (min_val, max_val) in RangeValidator.PV_MODULE_SPECS.items():
            if field not in data:
                continue
            
            value = data[field]
            if value is None or value == "Not available":
                continue
            
            try:
                val = float(value)
                if not (min_val <= val <= max_val):
                    return False, f"{field}={value} out of range [{min_val}-{max_val}]"
            except (ValueError, TypeError):
                continue
        
        return True, "PV Module specs valid"

    @staticmethod
    def validate_string_inverter(data: dict) -> tuple[bool, str]:
        """Validate string inverter specs"""
        for field, (min_val, max_val) in RangeValidator.STRING_INVERTER_SPECS.items():
            if field not in data:
                continue
            
            value = data[field]
            if value is None or value == "Not available":
                continue
            
            try:
                val = float(value)
                if not (min_val <= val <= max_val):
                    return False, f"{field}={value} out of range [{min_val}-{max_val}]"
            except (ValueError, TypeError):
                continue
        
        # Special check: max_dc_input_w should be > wattage_w
        if "max_dc_input_w" in data and "wattage_w" in data:
            try:
                max_dc = float(data["max_dc_input_w"])
                wattage = float(data["wattage_w"])
                if max_dc < wattage * 1.4:  # Should be at least 40% higher
                    return False, f"max_dc_input_w ({max_dc}W) should be > wattage ({wattage}W)"
            except (ValueError, TypeError):
                pass
        
        return True, "String inverter specs valid"

    @staticmethod
    def validate_microinverter(data: dict) -> tuple[bool, str]:
        """Validate microinverter specs"""
        for field, (min_val, max_val) in RangeValidator.MICROINVERTER_SPECS.items():
            if field not in data:
                continue
            
            value = data[field]
            if value is None or value == "Not available":
                continue
            
            try:
                val = float(value)
                if not (min_val <= val <= max_val):
                    return False, f"{field}={value} out of range [{min_val}-{max_val}]"
            except (ValueError, TypeError):
                continue
        
        return True, "Microinverter specs valid"

    @staticmethod
    def validate_battery(data: dict) -> tuple[bool, str]:
        """Validate battery/ESS specs"""
        for field, (min_val, max_val) in RangeValidator.BATTERY_SPECS.items():
            if field not in data:
                continue
            
            value = data[field]
            if value is None or value == "Not available":
                continue
            
            try:
                val = float(value)
                if not (min_val <= val <= max_val):
                    return False, f"{field}={value} out of range [{min_val}-{max_val}]"
            except (ValueError, TypeError):
                continue
        
        # Special check: usable <= total
        if "usable_capacity_kwh" in data and "total_capacity_kwh" in data:
            try:
                usable = float(data["usable_capacity_kwh"])
                total = float(data["total_capacity_kwh"])
                if usable > total:
                    return False, f"Usable capacity ({usable}kWh) > total ({total}kWh)"
            except (ValueError, TypeError):
                pass
        
        return True, "Battery specs valid"

    @staticmethod
    def validate_surge_protector(data: dict) -> tuple[bool, str]:
        """Validate surge protector specs"""
        for field, (min_val, max_val) in RangeValidator.SURGE_PROTECTOR_SPECS.items():
            if field not in data:
                continue
            
            value = data[field]
            if value is None or value == "Not available":
                continue
            
            try:
                val = float(value)
                if not (min_val <= val <= max_val):
                    return False, f"{field}={value} out of range [{min_val}-{max_val}]"
            except (ValueError, TypeError):
                continue
        
        return True, "Surge protector specs valid"

    @staticmethod
    def validate_combiner_box(data: dict) -> tuple[bool, str]:
        """Validate combiner box specs"""
        for field, (min_val, max_val) in RangeValidator.COMBINER_BOX_SPECS.items():
            if field not in data:
                continue
            
            value = data[field]
            if value is None or value == "Not available":
                continue
            
            try:
                val = float(value)
                if not (min_val <= val <= max_val):
                    return False, f"{field}={value} out of range [{min_val}-{max_val}]"
            except (ValueError, TypeError):
                continue
        
        return True, "Combiner box specs valid"

    @staticmethod
    def validate_by_subtype(equipment_sub_type: str, data: dict) -> tuple[bool, str]:
        """
        Validate specs based on equipment subtype
        
        Returns:
            (is_valid, message)
        """
        validators = {
            "pv_module": RangeValidator.validate_pv_module,
            "string_inverter": RangeValidator.validate_string_inverter,
            "microinverter": RangeValidator.validate_microinverter,
            "solaredge_inverter": RangeValidator.validate_string_inverter,
            "ess": RangeValidator.validate_battery,
            "surge_protector": RangeValidator.validate_surge_protector,
            "combiner_box": RangeValidator.validate_combiner_box
        }
        
        validator_func = validators.get(equipment_sub_type)
        if not validator_func:
            return True, f"No validator for {equipment_sub_type}"
        
        return validator_func(data)
