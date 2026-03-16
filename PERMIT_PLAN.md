# Plan: Extend Equipment Extraction to Support Permit Automation

## Executive Summary

Current extraction layer is **good for equipment specs** but **insufficient for permit plan generation**. To bridge the gap, we need a multi-phase approach that doesn't try to do everything at once.

**Recommendation**: Start with **Phase 1 (Schema Redesign)** to make the foundation permit-ready, then incrementally add extraction improvements and calculation layers.

---

## Current Status

### What Works Well ✅
- Equipment identity (manufacturer, model, type)
- Electrical ratings (voltage, current, power)
- Efficiency data
- Basic certifications (UL listing)
- Dimensions/weight (when available)

### What's Missing ❌
1. **Structured certification layer** (exact UL standards, NEC references)
2. **Permit-critical fields** (fire rating, fuse rating, temp limits, compatibility matrices)
3. **Structured nested data** (branch circuit limits, load tables)
4. **Proper typing** (mixed numbers/strings/booleans)
5. **Permit calculation inputs** (string sizing, wire sizing, OCPD data)
6. **Site/layout data** (completely absent)
7. **Structural/BOS data** (separate from equipment extraction)

---

## Proposed Solution: 4-Phase Approach

### PHASE 1: Schema Redesign (Week 1)
**Goal**: Define permit-ready schema structure per equipment type

#### Work Items

**1.1 Create Extended Schema Templates**
- PV Module: Add 12-15 permit fields
- String Inverter: Add 8-10 permit fields  
- Microinverter: Add 10-12 permit fields (with structured branch-circuit)
- Optimizer: Add 6-8 permit fields
- Battery/ESS: Add 15-20 permit fields
- Racking: Add 12-15 permit fields

**1.2 Define Field Categories**
For each equipment type:
- **Identity** (manufacturer, model, UL listing #)
- **Electrical Ratings** (voltage, current, power)
- **Thermal** (operating range, de-rate curve)
- **Mechanical** (weight, dimensions, load ratings)
- **Code/Certification** (UL, NEC, fire rating, interconnection)
- **Compatibility** (connectors, string limits, module compatibility)
- **Installation** (orientation, clearance, grounding)
- **Extraction Metadata** (confidence, source, notes)

**1.3 Standardize Data Types**
Rules:
```
- Numeric ratings: Always number, never string "123"
- Booleans: true/false, never "Yes"/"No"/"True"
- Unknown data: null (never "Not available")
- Ranges: Structured object {min, max, unit}
- Nested data: Structured object, not flat string
- Notes: Separate extraction_notes field
- Certifications: Array of objects with standard + ID
```

**1.4 Define Quality Tiers**
Each field gets a tier:
- **TIER 1** (must-have): Electrical & code-critical
  - Module: wattage, Voc, Isc, fire rating, connector
  - Inverter: AC power, DC voltage, OCPD max, startup voltage
  - Microinverter: peak power, branch limits (structured)
  - Battery: capacity, continuous power, max stack count
  - Racking: material, profile, roof types, uplift load

- **TIER 2** (important): System design inputs
  - Module efficiency, tolerance, series fuse, cell count, temp coefficients
  - Inverter MPPT voltage, DC inputs, power factor, voltage range
  - Microinverter temp range, ambient limits
  - Battery chemistry, AC/DC coupling, controller type
  - Racking attachment types, span limits, splice requirements

- **TIER 3** (nice-to-have): Optimization & reference
  - Compatible families, mounting constraints, thermal expansion
  - Ancillary specifications

**Deliverable**: `app/schemas/permit_schema.py` with extended classes

---

### PHASE 2: Extraction Improvements (Week 2)
**Goal**: Update Gemini prompts to extract permit fields with proper typing

#### Work Items

**2.1 Create Permit-Optimized Extraction Prompts**
For each equipment type, new Gemini prompt that:
- Explicitly asks for TIER 1 fields first
- Requests structured responses for complex fields
- Returns `null` if data truly unavailable (not "Not available")
- Validates against permit-ready schema
- Returns extraction metadata (confidence, data source)

Example structure for Gemini response:
```json
{
  "identity": {...},
  "electrical": {...},
  "thermal": {...},
  "mechanical": {...},
  "certifications": [
    {"standard": "UL 1741", "variant": "RD", "listing_id": "xxxxx"},
    {"standard": "IEEE 1547", "compliance": "yes"}
  ],
  "compatibility": {
    "connector_type": "MC4",
    "module_wattage_range_w": {"min": 300, "max": 420}
  },
  "extraction_metadata": {
    "data_source": "page 3-4",
    "confidence_score": 0.95,
    "extraction_notes": "De-rate curve found in appendix"
  }
}
```

**2.2 Update Field Extraction Rules**
```python
# In extraction_service.py

def extract_module_specs():
    """PV Module permit-ready extraction"""
    # TIER 1 fields (required effort)
    - wattage_w: number
    - voc_v: number with tolerance
    - isc_a: number with tolerance
    - fire_classification: "Class A" | "Class B" | "Class C"
    - recommended_series_fuse_a: number
    - connector_type: "MC4" | "MC3" | "Tyco" | ...
    - max_system_voltage_v: number
    
    # TIER 2 fields
    - module_efficiency_pct: number
    - power_tolerance_neg_pct: number
    - power_tolerance_pos_pct: number
    - cell_count: number
    - operating_temp_min_c: number (not string "-40")
    - operating_temp_max_c: number
    - temperature_coefficient_pmax: number
    
    # TIER 3 fields
    - max_static_load_front_pa: number
    - max_static_load_rear_pa: number
    - mounting_orientation_constraints: string | null
```

**2.3 Add Schema Validation**
```python
# After extraction, validate:
class PermitSchemaValidator:
    - Check that TIER 1 fields are not null
    - Verify numeric fields are numeric (not strings)
    - Ensure certifications are structured (not boolean)
    - Validate ranges make sense (min < max)
    - Confirm extraction_metadata is populated
```

**2.4 Update Response Normalization**
Update `_normalize_specifications()` to:
- Be schema-aware (know what each field requires)
- Enforce type conversions: "123" → 123, "True" → true
- Reject "Not available" → require null or best estimate + note
- Expand single values into structured form where needed

**Deliverable**: Updated extraction prompts + validation logic

---

### PHASE 3: Permit Calculation Layer (Phase 2 - Separate)
**Goal**: Separate service to compute permit values from equipment specs

**Not in this sprint**, but architecture should allow it.

```
Input: Equipment specs (from Phase 1-2)
       Site data (modules, voltage, etc.)

Output: Permit calculations
  - String voltage (Vmp × n modules)
  - String current (Isc + ~1.25)
  - OCPD rating (string current × 1.25)
  - Conductor size (based on current, temp, voltage)
  - System voltage drop
  - Module string count reliability
  - Inverter loading %
```

**This is a separate service** (`permit_calculations_service.py`) that takes clean specs and produces permit calculations.

---

### PHASE 4: Structural/BOS Layer (Phase 3 - Future)
**Goal**: Handle site-specific and structural permit data

**Not in this sprint**, future work.

```
Inputs: Racking specs + site data (roof type, wind zone, orientation)
        Module specs (weight, dimensions)
        
Outputs: Structural permit data
  - Attachment plan
  - Load distribution tables
  - Uplift calculations
  - Fastener compatibility
  - BOS component list (disconnects, breakers, conduit sizes)
```

---

## Implementation Timeline

```
Week 1 (PHASE 1): Schema Design
  Mon-Wed: Extended schemas for all equipment types
  Thu-Fri: Review, adjustment, approval

Week 2 (PHASE 2): Extraction Improvements
  Mon-Wed: Update Gemini prompts + validation
  Thu-Fri: Testing, refinement

Week 3+: Calculation Layers (future phases)
  Phase 3: Permit calculations
  Phase 4: Structural/BOS (later)
```

---

## Scope by Equipment Type

### Priority 1: String Inverter (Critical for permit)
- [ ] AC output power (explicit, not assumed from DC)
- [ ] AC breaker/OCPD maximum
- [ ] Startup voltage
- [ ] MPPT voltage window
- [ ] Nominal DC input voltage
- [ ] DC inputs count
- [ ] Power factor
- [ ] Utility interconnection type (UG, OH, etc.)
- [ ] Exact UL 1741 variant (RD, SA, etc.)

### Priority 2: Microinverter (Critical for permit)
- [ ] **Structured branch circuit limits** (NOT just "20")
  ```json
  {
    "max_units_per_branch_circuit_240v_20a": 10,
    "max_units_per_branch_circuit_240v_15a": 7,
    "max_units_per_branch_circuit_208v": 8
  }
  ```
- [ ] Q-cable/trunk maximum units
- [ ] Output VA vs W distinction
- [ ] Reactive power capability
- [ ] Gateway/comm controller dependency
- [ ] Ambient temperature range
- [ ] Proper weight/dimensions (not "Not available")

### Priority 3: PV Module
- [ ] Fire classification (Class A/B/C)
- [ ] Series fuse rating
- [ ] Connector type
- [ ] Max static load (front/rear)
- [ ] Operating temp min/max (as numbers)
- [ ] Module efficiency %

### Priority 4: Battery/ESS
- [ ] Chemistry type
- [ ] Max parallel stack count
- [ ] AC-coupled vs DC-coupled
- [ ] Controller/gateway requirement
- [ ] Fire setback distance (if applicable)
- [ ] Approved locations (indoor/outdoor/garage/etc)

### Priority 5: Racking/Mounting
- [ ] Exact profile/family designation
- [ ] Roof type compatibility matrix
- [ ] Allowable span limits (by wind/snow)
- [ ] Approved attachment hardware families
- [ ] Uplift load per attachment
- [ ] Installation orientation limits

---

## Success Criteria

### Phase 1 Complete When:
- [ ] All equipment types have extended schema
- [ ] TIER 1 fields defined per type
- [ ] Data types standardized (no mixed types)
- [ ] Quality tiers assigned
- [ ] Schemas pass review/approval

### Phase 2 Complete When:
- [ ] Gemini prompts updated for all types
- [ ] TIER 1 fields extracted with >90% success
- [ ] Validation passes for 95% of extractions
- [ ] Type conversions working properly
- [ ] "Not available" replaced with null + notes

### Overall Success:
- [ ] Module extraction feeds electrical design
- [ ] Inverter extraction feeds OCPD selection  
- [ ] Microinverter extraction feeds branch circuit plan
- [ ] Battery extraction feeds interconnection decision
- [ ] Racking extraction feeds structural review
- [ ] Data is structured, typed, and permittable

---

## Resources Needed

- **You**: Approval of schema design (1 hour review)
- **Me**: Implementation of phases (10-15 hours estimated)
- **Testing**: Sample permit documents to validate against (you provide)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Gemini model can't extract permit fields | Use examples from real datasheets in prompt |
| Schema becomes too complex | Keep TIER 1 focused, TIER 2/3 optional |
| Extraction loses data quality | Validation layer catches errors |
| Over-engineering for future use | Stop at permit-ready layer, don't add calculation yet |

---

## Next Steps

### If You Approve This Plan:
1. ✅ I create extended schemas for all equipment types
2. ✅ You review and approve (or request changes)
3. ✅ I update Gemini prompts & validation
4. ✅ We test on real datasheets
5. ✅ Demo extraction with full permit fields
6. ✅ Plan Phase 3/4 (calculation layers) separately

### If You Want Changes:
- Adjust scope (skip certain equipment types)
- Change priorities (do Microinverter first, Racking later)
- Add more fields or reduce to MVP
- Split timeline differently

---

## Decision Required

**What should I do?**

A) **APPROVE**: Start Phase 1 (Schema design this week)

B) **MODIFY**: Change scope/priority/timeline, then proceed

C) **DEFER**: Don't do permit layer yet, focus on basic extraction quality first

D) **EXPAND**: Include Phase 3 (permit calculations) in initial scope

**Please choose, and I'll proceed accordingly.** 🚀
