# ==============================================================================
# services/validation/cross_field_validator.py
# ==============================================================================
# PURPOSE
#   Cross-field validation for equipment specifications.
#   Validates electrical engineering relationships (Power = V×I, etc.)
#   Used in PASS 5 of the 6-stage extraction pipeline.
# ==============================================================================

import logging
import re

logger = logging.getLogger(__name__)


class CrossFieldValidator:
    """Validates cross-field electrical engineering relationships"""
    
    def __init__(self):
        self.POWER_FACTOR = 0.95  # Typical AC power factor
        self.MISMATCH_THRESHOLD = 0.10  # 10% mismatch triggers repair

    @staticmethod
    def _to_number(value):
        """Safely coerce common numeric string formats (e.g. '240 V', '1,200W') to float."""
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None

            match = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", cleaned)
            if not match:
                return None

            numeric_text = match.group().replace(",", "")
            try:
                return float(numeric_text)
            except ValueError:
                return None

        return None
    
    def validate(
        self,
        data: dict,
        equipment_sub_type: str
    ) -> tuple[list, dict]:
        """
        Validate cross-field relationships for equipment type.
        
        Returns:
            (violations: list, details: dict)
            - violations: list of error messages (empty = all good)
            - details: dict with calculated values and results for PASS 6
        """
        violations = []
        details = {}
        
        if equipment_sub_type == "pv_module":
            violations, details = self._validate_pv_module(data)
        elif equipment_sub_type == "ac_module":
            violations, details = self._validate_ac_module(data)
        elif equipment_sub_type in ("string_inverter", "solaredge_inverter"):
            violations, details = self._validate_string_inverter(data)
        elif equipment_sub_type == "microinverter":
            violations, details = self._validate_microinverter(data)
        elif equipment_sub_type == "se_optimizer":
            violations, details = self._validate_se_optimizer(data)
        elif equipment_sub_type == "ess":
            violations, details = self._validate_battery_ess(data)
        elif "disconnect" in equipment_sub_type:
            violations, details = self._validate_disconnect(data)
        elif equipment_sub_type == "combiner_box":
            violations, details = self._validate_combiner_box(data)
        
        return violations, details
    
    # ========================================================================
    # PV MODULE
    # ========================================================================
    def _validate_pv_module(self, data: dict) -> tuple[list, dict]:
        violations = []
        details = {}
        
        power_w = self._to_number(data.get("wattage_w"))
        vmp_v = self._to_number(data.get("vmp_v"))
        imp_a = self._to_number(data.get("imp_a"))
        voc_v = self._to_number(data.get("voc_v"))
        isc_a = self._to_number(data.get("isc_a"))
        max_sys_v = self._to_number(data.get("max_system_voltage_v"))
        
        # Rule 1: Power = Vmp × Imp
        if power_w and vmp_v and imp_a:
            calculated_power = vmp_v * imp_a
            mismatch = abs(power_w - calculated_power) / max(calculated_power, 1)
            details["power_calculation"] = {
                "extracted": power_w,
                "calculated": calculated_power,
                "mismatch_pct": round(mismatch * 100, 2)
            }
            if mismatch > self.MISMATCH_THRESHOLD:
                violations.append(
                    f"Power mismatch: extracted {power_w}W but Vmp×Imp = {calculated_power}W ({mismatch*100:.1f}% error)"
                )
        
        # Rule 2: Voltage hierarchy (Voc > Vmp by 10-30%)
        if voc_v and vmp_v:
            ratio = (voc_v - vmp_v) / vmp_v
            details["voltage_hierarchy"] = {
                "voc": voc_v,
                "vmp": vmp_v,
                "voc_higher_pct": round(ratio * 100, 2)
            }
            if voc_v <= vmp_v:
                violations.append(f"Voltage error: Voc ({voc_v}V) should be > Vmp ({vmp_v}V)")
            elif ratio < 0.05:
                violations.append(f"Voltage hierarchy: Voc only {ratio*100:.1f}% higher than Vmp (expected 10-30%)")
        
        # Rule 3: Current hierarchy (Isc > Imp by 5-15%)
        if isc_a and imp_a:
            ratio = (isc_a - imp_a) / imp_a
            details["current_hierarchy"] = {
                "isc": isc_a,
                "imp": imp_a,
                "isc_higher_pct": round(ratio * 100, 2)
            }
            if isc_a <= imp_a:
                violations.append(f"Current error: Isc ({isc_a}A) should be > Imp ({imp_a}A)")
            elif ratio < 0.02:
                violations.append(f"Current hierarchy: Isc only {ratio*100:.1f}% higher than Imp (expected 5-15%)")
        
        # Rule 4: System voltage >= Voc
        if max_sys_v and voc_v:
            if max_sys_v < voc_v:
                violations.append(f"System voltage constraint: max_system_voltage ({max_sys_v}V) must be ≥ Voc ({voc_v}V)")
        
        return violations, details
    
    # ========================================================================
    # AC MODULE
    # ========================================================================
    def _validate_ac_module(self, data: dict) -> tuple[list, dict]:
        violations = []
        details = {}
        
        module_power = self._to_number(data.get("module_power_w"))
        ac_output = self._to_number(data.get("ac_output_power_w"))
        voltage_v = self._to_number(data.get("grid_voltage_v"))
        current_a = self._to_number(data.get("max_output_current_a"))
        efficiency = self._to_number(data.get("efficiency_pct"))
        
        # Rule 1: AC Power = V × I × PF
        if voltage_v and current_a:
            calculated_power = voltage_v * current_a * self.POWER_FACTOR
            details["ac_power_calculation"] = {
                "voltage": voltage_v,
                "current": current_a,
                "power_factor": self.POWER_FACTOR,
                "calculated_power": calculated_power
            }
            if ac_output:
                mismatch = abs(ac_output - calculated_power) / max(calculated_power, 1)
                details["ac_power_calculation"]["extracted_power"] = ac_output
                details["ac_power_calculation"]["mismatch_pct"] = round(mismatch * 100, 2)
                if mismatch > self.MISMATCH_THRESHOLD:
                    violations.append(
                        f"AC Power mismatch: extracted {ac_output}W but V×I×PF = {calculated_power}W ({mismatch*100:.1f}% error)"
                    )
        
        # Rule 2: Efficiency = AC / DC
        if ac_output and module_power:
            calc_efficiency = (ac_output / module_power) * 100
            details["efficiency_calculation"] = {
                "ac_output": ac_output,
                "module_power": module_power,
                "calculated_efficiency": round(calc_efficiency, 2)
            }
            if efficiency:
                eff_mismatch = abs(efficiency - calc_efficiency) / max(calc_efficiency, 1)
                details["efficiency_calculation"]["extracted_efficiency"] = efficiency
                details["efficiency_calculation"]["mismatch_pct"] = round(eff_mismatch * 100, 2)
                if eff_mismatch > 0.05:  # 5% tolerance
                    violations.append(
                        f"Efficiency mismatch: extracted {efficiency}% but AC/DC = {calc_efficiency:.1f}%"
                    )
        
        return violations, details
    
    # ========================================================================
    # STRING INVERTER
    # ========================================================================
    def _validate_string_inverter(self, data: dict) -> tuple[list, dict]:
        violations = []
        details = {}
        
        ac_power = self._to_number(data.get("wattage_w"))
        dc_power = self._to_number(data.get("max_dc_input_w"))
        ac_voltage = self._to_number(data.get("nominal_ac_voltage_v"))
        ac_current = self._to_number(data.get("max_ac_output_current_a"))
        peak_eff = self._to_number(data.get("peak_efficiency_pct"))
        cec_eff = self._to_number(data.get("cec_efficiency_pct"))
        phase = data.get("phase")
        frequency = self._to_number(data.get("frequency_hz"))
        
        # Rule 1: AC Power = V × I × PF
        if ac_voltage and ac_current:
            calculated_power = ac_voltage * ac_current * self.POWER_FACTOR
            details["ac_power_calculation"] = {
                "voltage": ac_voltage,
                "current": ac_current,
                "power_factor": self.POWER_FACTOR,
                "calculated_power": int(calculated_power)
            }
            if ac_power:
                mismatch = abs(ac_power - calculated_power) / max(calculated_power, 1)
                details["ac_power_calculation"]["extracted_power"] = ac_power
                details["ac_power_calculation"]["mismatch_pct"] = round(mismatch * 100, 2)
                if mismatch > self.MISMATCH_THRESHOLD:
                    violations.append(
                        f"AC Power mismatch: extracted {ac_power}W but V×I×PF = {int(calculated_power)}W ({mismatch*100:.1f}% error)"
                    )
        
        # Rule 2: DC-AC Ratio (0.8-1.2)
        if ac_power and dc_power:
            ratio = ac_power / dc_power if dc_power > 0 else 0
            details["dc_ac_ratio"] = {
                "ac_power": ac_power,
                "dc_power": dc_power,
                "ratio": round(ratio, 3)
            }
            if ratio < 0.8 or ratio > 1.2:
                violations.append(
                    f"DC-AC ratio unusual: AC {ac_power}W / DC {dc_power}W = {ratio:.2f} (expected 0.8-1.2)"
                )
        
        # Rule 3: Efficiency bounds
        if peak_eff and cec_eff:
            if peak_eff < cec_eff:
                violations.append(f"Efficiency error: peak ({peak_eff}%) should be ≥ CEC ({cec_eff}%)")
            if peak_eff - cec_eff > 5:
                violations.append(f"Efficiency gap too large: peak-CEC = {peak_eff - cec_eff}% (expected 1-3%)")
            details["efficiency"] = {
                "peak": peak_eff,
                "cec": cec_eff,
                "gap": peak_eff - cec_eff if peak_eff else None
            }
        
        # Rule 4: Phase-Voltage consistency
        if phase and ac_voltage:
            single_phase_voltages = [120, 208, 240, 277]
            three_phase_voltages = [208, 240, 277, 347, 480]
            
            details["phase_voltage"] = {
                "phase": phase,
                "voltage": ac_voltage
            }
            
            if "single" in str(phase).lower():
                if int(round(ac_voltage)) not in single_phase_voltages:
                    violations.append(
                        f"Single-phase voltage error: {ac_voltage}V not in {single_phase_voltages}"
                    )
            elif "3" in str(phase):
                if int(round(ac_voltage)) not in three_phase_voltages:
                    violations.append(
                        f"3-phase voltage error: {ac_voltage}V not in {three_phase_voltages}"
                    )
        
        # Rule 5: Frequency validity
        if frequency:
            details["frequency"] = frequency
            if int(round(frequency)) not in [50, 60]:
                violations.append(f"Frequency error: {frequency}Hz must be 50 or 60")
        
        return violations, details
    
    # ========================================================================
    # MICROINVERTER
    # ========================================================================
    # def _validate_microinverter(self, data: dict) -> tuple[list, dict]:
    #     violations = []
    #     details = {}
        
    #     dc_power = self._to_number(data.get("max_input_power_w"))
    #     ac_power = self._to_number(data.get("peak_output_power_w"))
    #     ac_voltage = self._to_number(data.get("nominal_ac_voltage_v"))
    #     ac_current = self._to_number(data.get("max_ac_output_current_a"))
    #     min_mppt = self._to_number(data.get("min_mppt_voltage_v"))
    #     max_mppt = self._to_number(data.get("max_mppt_voltage_v"))
    #     peak_eff = self._to_number(data.get("peak_efficiency_pct"))
    #     cec_eff = self._to_number(data.get("cec_efficiency_pct"))
        
    #     # Rule 1: AC Power = V × I × PF
    #     if ac_voltage and ac_current:
    #         calculated_power = ac_voltage * ac_current * self.POWER_FACTOR
    #         details["ac_power_calculation"] = {
    #             "voltage": ac_voltage,
    #             "current": ac_current,
    #             "calculated_power": int(calculated_power)
    #         }
    #         if ac_power:
    #             mismatch = abs(ac_power - calculated_power) / max(calculated_power, 1)
    #             details["ac_power_calculation"]["extracted_power"] = ac_power
    #             details["ac_power_calculation"]["mismatch_pct"] = round(mismatch * 100, 2)
    #             if mismatch > self.MISMATCH_THRESHOLD:
    #                 violations.append(
    #                     f"AC Power mismatch: {ac_power}W but V×I×PF = {int(calculated_power)}W ({mismatch*100:.1f}% error)"
    #                 )
        
    #     # Rule 2: Efficiency = AC / DC
    #     if ac_power and dc_power:
    #         calc_eff = (ac_power / dc_power) * 100
    #         details["efficiency"] = {
    #             "ac": ac_power,
    #             "dc": dc_power,
    #             "calculated_efficiency": round(calc_eff, 2)
    #         }
    #         if cec_eff and abs(cec_eff - calc_eff) / max(calc_eff, 1) > 0.05:
    #             violations.append(f"CEC efficiency {cec_eff}% but AC/DC = {calc_eff:.1f}%")
        
    #     # Rule 3: MPPT Voltage Range
    #     if min_mppt and max_mppt:
    #         details["mppt_range"] = {
    #             "min": min_mppt,
    #             "max": max_mppt
    #         }
    #         if min_mppt >= max_mppt:
    #             violations.append(f"MPPT error: min_voltage ({min_mppt}V) must be < max_voltage ({max_mppt}V)")
    #         ratio = min_mppt / max_mppt
    #         if ratio < 0.1:
    #             violations.append(f"MPPT range suspicious: min is only {ratio*100:.1f}% of max (expected >10%)")
        
    #     return violations, details
    
    # ========================================================================
    # MICROINVERTER
    # ========================================================================
    def _validate_microinverter(self, data: dict) -> tuple[list, dict]:
        violations = []
        details = {}

        max_input_power = self._to_number(data.get("max_input_power_w"))
        peak_output_power = self._to_number(data.get("peak_output_power_w"))
        ac_voltage = self._to_number(data.get("nominal_ac_voltage_v"))
        ac_current = self._to_number(data.get("max_ac_output_current_a"))
        min_mppt = self._to_number(data.get("min_mppt_voltage_v"))
        max_mppt = self._to_number(data.get("max_mppt_voltage_v"))
        max_input_voltage = self._to_number(data.get("max_input_voltage_v"))
        max_input_current = self._to_number(data.get("max_input_current_a"))
        peak_eff = self._to_number(data.get("peak_efficiency_pct"))
        cec_eff = self._to_number(data.get("cec_efficiency_pct"))

        # Rule 1: AC-side soft consistency check
        if ac_voltage and ac_current:
            calculated_apparent_power = ac_voltage * ac_current * self.POWER_FACTOR
            details["ac_power_check"] = {
                "voltage_v": ac_voltage,
                "current_a": ac_current,
                "calculated_power_w": round(calculated_apparent_power, 2),
            }

            if peak_output_power:
                mismatch = abs(peak_output_power - calculated_apparent_power) / max(calculated_apparent_power, 1)
                details["ac_power_check"]["peak_output_power_w"] = peak_output_power
                details["ac_power_check"]["mismatch_pct"] = round(mismatch * 100, 2)

                if mismatch > 0.15:
                    violations.append(
                        f"AC-side power looks suspicious: peak_output_power={peak_output_power}W "
                        f"but V×I×PF={calculated_apparent_power:.1f}W."
                    )

        # Rule 2: MPPT range validation
        if min_mppt and max_mppt:
            details["mppt_range"] = {
                "min_v": min_mppt,
                "max_v": max_mppt
            }

            if min_mppt >= max_mppt:
                violations.append(
                    f"MPPT error: min_mppt_voltage ({min_mppt}V) must be < max_mppt_voltage ({max_mppt}V)"
                )

            ratio = min_mppt / max_mppt
            details["mppt_range"]["ratio"] = round(ratio, 4)

            if ratio < 0.1:
                violations.append(
                    f"MPPT range suspicious: min is only {ratio * 100:.1f}% of max (expected >10%)"
                )

        # Rule 3: Voltage hierarchy validation
        if min_mppt and max_mppt and max_input_voltage:
            details["voltage_hierarchy"] = {
                "min_mppt_v": min_mppt,
                "max_mppt_v": max_mppt,
                "max_input_voltage_v": max_input_voltage,
            }

            if not (min_mppt < max_mppt < max_input_voltage):
                violations.append(
                    f"Voltage hierarchy invalid: expected min_mppt < max_mppt < max_input_voltage, "
                    f"got {min_mppt}V < {max_mppt}V < {max_input_voltage}V"
                )

        # Rule 4: Efficiency sanity checks
        if peak_eff or cec_eff:
            details["efficiency_sanity"] = {}

        if peak_eff:
            details["efficiency_sanity"]["peak_efficiency_pct"] = peak_eff
            if not (90 <= peak_eff <= 100):
                violations.append(f"Peak efficiency suspicious: {peak_eff}%")

        if cec_eff:
            details["efficiency_sanity"]["cec_efficiency_pct"] = cec_eff
            if not (90 <= cec_eff <= 100):
                violations.append(f"CEC efficiency suspicious: {cec_eff}%")

        if peak_eff and cec_eff:
            if cec_eff > peak_eff:
                violations.append(
                    f"CEC efficiency {cec_eff}% should not exceed peak efficiency {peak_eff}%"
                )

        # Rule 5: Loose DC upper-bound sanity check
        if max_mppt and max_input_current and max_input_power:
            theoretical_dc_limit = max_mppt * max_input_current
            details["dc_upper_bound"] = {
                "max_mppt_voltage_v": max_mppt,
                "max_input_current_a": max_input_current,
                "theoretical_limit_w": round(theoretical_dc_limit, 2),
                "max_input_power_w": max_input_power,
            }

            if max_input_power > theoretical_dc_limit * 1.10:
                violations.append(
                    f"Max input power {max_input_power}W exceeds rough DC upper bound {theoretical_dc_limit:.1f}W"
                )

        return violations, details
    
    # ========================================================================
    # SE OPTIMIZER
    # ========================================================================
    def _validate_se_optimizer(self, data: dict) -> tuple[list, dict]:
        violations = []
        details = {}
        
        input_power = self._to_number(data.get("rated_input_power_w"))
        input_voltage = self._to_number(data.get("max_input_voltage_v"))
        input_current = self._to_number(data.get("max_input_current_a"))
        peak_eff = self._to_number(data.get("peak_efficiency_pct"))
        weighted_eff = self._to_number(data.get("weighted_efficiency_pct"))
        
        # Rule 1: Power = V × I
        if input_voltage and input_current:
            calculated_power = input_voltage * input_current
            details["input_power_calculation"] = {
                "voltage": input_voltage,
                "current": input_current,
                "calculated_power": int(calculated_power)
            }
            if input_power:
                mismatch = abs(input_power - calculated_power) / max(calculated_power, 1)
                details["input_power_calculation"]["extracted_power"] = input_power
                details["input_power_calculation"]["mismatch_pct"] = round(mismatch * 100, 2)
                if mismatch > self.MISMATCH_THRESHOLD:
                    violations.append(
                        f"Power mismatch: {input_power}W but V×I = {int(calculated_power)}W ({mismatch*100:.1f}% error)"
                    )
        
        # Rule 2: Efficiency bounds
        if peak_eff and weighted_eff:
            if peak_eff < weighted_eff:
                violations.append(f"Efficiency error: peak ({peak_eff}%) must be ≥ weighted ({weighted_eff}%)")
            details["efficiency"] = {
                "peak": peak_eff,
                "weighted": weighted_eff,
                "gap": peak_eff - weighted_eff if peak_eff else None
            }
        
        return violations, details
    
    # ========================================================================
    # BATTERY / ESS
    # ========================================================================
    def _validate_battery_ess(self, data: dict) -> tuple[list, dict]:
        violations = []
        details = {}
        
        usable_capacity = self._to_number(data.get("usable_capacity_kwh"))
        total_capacity = self._to_number(data.get("total_capacity_kwh"))
        continuous_power = self._to_number(data.get("max_continuous_power_w"))
        peak_power = self._to_number(data.get("peak_power_w"))
        nominal_voltage = self._to_number(data.get("nominal_voltage_v"))
        max_discharge_current = self._to_number(data.get("max_discharge_current_a"))
        dod = self._to_number(data.get("depth_of_discharge_pct"))
        efficiency = self._to_number(data.get("round_trip_efficiency_pct"))
        
        # Rule 1: Usable ≤ Total
        if usable_capacity and total_capacity:
            ratio = usable_capacity / total_capacity if total_capacity > 0 else 0
            details["capacity"] = {
                "usable": usable_capacity,
                "total": total_capacity,
                "ratio": round(ratio, 3)
            }
            if usable_capacity > total_capacity:
                violations.append(f"Capacity error: usable ({usable_capacity}kWh) > total ({total_capacity}kWh)")
            if ratio < 0.8:
                violations.append(f"Capacity ratio low: usable only {ratio*100:.1f}% of total (expected 80-100%)")
        
        # Rule 2: Power = V × I
        if nominal_voltage and max_discharge_current:
            calculated_power = (nominal_voltage * max_discharge_current) / 1000  # Convert to kW, then W
            calculated_power_w = nominal_voltage * max_discharge_current
            details["power_calculation"] = {
                "voltage": nominal_voltage,
                "current": max_discharge_current,
                "calculated_power_w": int(calculated_power_w)
            }
            if continuous_power:
                mismatch = abs(continuous_power - calculated_power_w) / max(calculated_power_w, 1)
                details["power_calculation"]["extracted_power"] = continuous_power
                details["power_calculation"]["mismatch_pct"] = round(mismatch * 100, 2)
                if mismatch > self.MISMATCH_THRESHOLD:
                    violations.append(
                        f"Power mismatch: {continuous_power}W but V×I = {int(calculated_power_w)}W ({mismatch*100:.1f}% error)"
                    )
        
        # Rule 3: Peak ≥ Continuous
        if peak_power and continuous_power:
            if peak_power < continuous_power:
                violations.append(f"Power error: peak ({peak_power}W) should be ≥ continuous ({continuous_power}W)")
            ratio = peak_power / continuous_power if continuous_power > 0 else 0
            details["power_hierarchy"] = {
                "peak": peak_power,
                "continuous": continuous_power,
                "ratio": round(ratio, 2)
            }
        
        # Rule 4: Energy-Time validity
        if usable_capacity and continuous_power:
            hours = (usable_capacity * 1000) / max(continuous_power, 1)  # Convert kWh to Wh
            details["energy_time"] = {
                "usable_capacity_kwh": usable_capacity,
                "power_w": continuous_power,
                "discharge_hours": round(hours, 2)
            }
            if hours < 0.25 or hours > 8:
                violations.append(f"Discharge time unusual: {hours:.2f} hours (expected 0.5-4 hours for batteries)")
        
        return violations, details
    
    # ========================================================================
    # DISCONNECT / BREAKER
    # ========================================================================
    def _validate_disconnect(self, data: dict) -> tuple[list, dict]:
        violations = []
        details = {}
        
        max_voltage = self._to_number(data.get("max_voltage_v"))
        max_current = self._to_number(data.get("max_current_a"))
        fuse_rating = self._to_number(data.get("fuse_rating_a"))
        
        # Rule 1: Fuse ≤ Current
        if fuse_rating and max_current:
            details["fuse_check"] = {
                "fuse_rating": fuse_rating,
                "max_current": max_current
            }
            if fuse_rating > max_current:
                violations.append(f"Fuse error: rating ({fuse_rating}A) must be ≤ max current ({max_current}A)")
        
        # Rule 2: Standard voltage check
        if max_voltage:
            dc_standard = [125, 250, 600, 1000]
            ac_standard = [120, 208, 240, 277, 347, 480]
            all_standard = set(dc_standard + ac_standard)
            
            details["voltage_standard"] = {
                "voltage": max_voltage
            }
            if int(round(max_voltage)) not in all_standard:
                violations.append(f"Voltage warning: {max_voltage}V not a standard rating")
        
        return violations, details
    
    # ========================================================================
    # COMBINER BOX
    # ========================================================================
    def _validate_combiner_box(self, data: dict) -> tuple[list, dict]:
        violations = []
        details = {}
        
        max_output_current = self._to_number(data.get("max_output_current_a"))
        fuse_rating = self._to_number(data.get("fuse_rating_a"))
        num_inputs = self._to_number(data.get("number_of_inputs"))
        max_voltage = self._to_number(data.get("max_input_voltage_v"))
        
        # Rule: Fuse ≤ Output Current
        if fuse_rating and max_output_current:
            details["fuse_output_check"] = {
                "fuse_rating": fuse_rating,
                "max_output_current": max_output_current
            }
            if fuse_rating > max_output_current:
                violations.append(f"Fuse error: ({fuse_rating}A) must be ≤ output current ({max_output_current}A)")
        
        return violations, details
