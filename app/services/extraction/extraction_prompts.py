# ==============================================================================
# services/extraction/extraction_prompts.py
# ==============================================================================
# PURPOSE
#   Prompt builders for the active 4-pass extraction pipeline
# ==============================================================================


class PromptBuilder:
    """Builds prompts for active extraction stages"""

    @staticmethod
    def _field_description(field: str, schema_template: dict) -> str:
        """Return a safe description even when schema values are null or malformed."""
        config = schema_template.get(field)
        if isinstance(config, dict):
            description = config.get("description")
            if isinstance(description, str) and description.strip():
                return description
        return "No description"

    # ========== PASS 1: Extract from PDF ==========

    @staticmethod
    def build_pass1_prompt(
        manufacturer: str,
        model: str,
        schema_template: dict,
        alias_guide: dict
    ) -> str:
        """PASS 1: Extract specs directly from PDF using Gemini 2.5 Pro (table-focused)"""
        field_list = "\n".join([
            f"  - {field}: {PromptBuilder._field_description(field, schema_template)}"
            for field in schema_template.keys()
        ])

        alias_text = ""
        if alias_guide:
            alias_text = "\n\n🔑 FIELD ALIASES (names used in datasheets):\n" + "\n".join([
                f"  - {field}: {', '.join(aliases)}"
                for field, aliases in alias_guide.items()
            ])

        return f"""You are a TECHNICAL DATASHEET EXTRACTION EXPERT. Your task is to read this PDF and extract EXACT electrical specifications from specification tables.

📋 EQUIPMENT DETAILS:
  Manufacturer: {manufacturer}
  Model: {model}

🎯 FIELDS TO EXTRACT:
{field_list}{alias_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ TABLE EXTRACTION STRATEGY (CRITICAL):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ LOCATE SPECIFICATION TABLES:
   Look for sections titled (commonly):
   - "Electrical Specifications"
   - "Technical Specifications"
   - "Performance Ratings"
   - "DC Output Specifications"
   - "AC Output Specifications"
   - "STC (Standard Test Conditions)" table
   - Any highlighted or colored tables with specs

2️⃣ UNDERSTAND TABLE STRUCTURE:
   Specs tables have:
   - LEFT COLUMN: Parameter names (VOC, ISC, Pmax, Efficiency, etc.)
   - MIDDLE/RIGHT COLUMNS: Values under different conditions (STC, NOCT, PTC)
   - ROW HEADERS: Show what each row measures
   - Use STC (Standard Test Conditions) values as primary source

3️⃣ EXTRACT VALUES FROM TABLE ROWS:
   Watch for these patterns:
   ✓ VOC / Voc / V_oc / Open Circuit Voltage → extract as voc_v
   ✓ ISC / Isc / I_sc / Short Circuit Current → extract as isc_a
   ✓ Pmax / P_max / Maximum Power / Rated Power → extract as wattage_w
   ✓ Efficiency / Conversion Efficiency → extract as efficiency_pct
   ✓ Temperature Coefficients / Temp Coef → extract as temp_coef_*

4️⃣ VALUE EXTRACTION RULES:
   - Extract EXACT numeric values from tables
   - Include units if table shows them (V, A, W, %, °C)
   - If value has range, use nominal/typical (middle) value
   - STC values are PREFERRED over NOCT or PTC
   - For missing STC, use available condition value

5️⃣ SPECIAL CASES:
   - If specs split across multiple tables: MERGE results (e.g., DC table + AC table)
   - Colored boxes often highlight key specs: CHECK these areas
   - Footnotes with superscript: Find matching notes at table bottom
   - Values in multiple columns: Use STC (Standard Test Condition) column if present

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ CRITICAL REQUIREMENTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ ONLY extract values that appear in specification TABLES (not marketing text)
✓ Extract ALL fields listed above if they appear in the table
✓ Do NOT invent, infer, or calculate values
✓ Do NOT use marketing claims, use technical specs only
✓ Return values as extracted (exact format from datasheet)
✓ Return ONLY valid JSON, no markdown, no explanations
✓ If a field NOT in the datasheet, omit it (return empty object for that field's value)

📝 JSON FORMAT (EXACT):
{{"voc_v": "value", "isc_a": "value", "wattage_w": "value", ...}}

Examples:
  ✅ GOOD: {{"voc_v": "40.2", "isc_a": "10.5", "wattage_w": "420"}}
  ❌ AVOID: {{"voc_v": null, "isc_a": "Not available", ...}} (leave out missing fields)
  ❌ WRONG: {{"note": "Specifications not found in PDF"}} (EXTRACT THE TABLE!)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NOW READ THE PDF AND EXTRACT ALL ELECTRICAL SPECIFICATIONS FROM THE TABLE(S).
Focus on finding the specification table first, then extract values systematically."""

    # ========== PASS 2: Web Search for Missing Fields ==========

    @staticmethod
    def build_pass2_repair_prompt(
        manufacturer: str,
        model: str,
        extracted: dict,
        critical_missing: list,
        schema_template: dict,
        equipment_sub_type: str = None
    ) -> str:
        """PASS 2: WEB SEARCH - Find missing specs from web sources"""
        current_values = "\n".join([
            f"  {k}: {v}" for k, v in extracted.items() if v and v != "Not available"
        ]) or "  (none found yet)"

        missing_fields = "\n".join([
            f"  - {field}" for field in critical_missing
        ])

        # PV MODULE SPECIFIC GUIDANCE
        pv_module_guidance = ""
        if equipment_sub_type and "module" in equipment_sub_type.lower():
            pv_module_guidance = """
FOR PV MODULES - Look specifically for these electrical values in datasheets:
  voc_v          → Open-circuit voltage (usually 30-80V per module)
  vmp_v          → Voltage at maximum power point  
  isc_a          → Short-circuit current (usually 8-15A)
  imp_a          → Current at maximum power point
  wattage_w      → Power rating (common: 300W, 400W, 500W, 550W, 600W+)
  temperature_coefficient_pmax → Usually negative, like -0.27%/°C
  
EXTRACTION RULES FOR MODULES:
  - Each value must have its unit (V, A, W, %/°C, etc.)
  - Never merge table cells. Each spec is independent
  - Example: "5.76 kW" → extract as "5760" (value only, convert to base unit)
  - Voc is NOT Vmp. Don't confuse them
  - Isc is NOT Imp. Check the label carefully"""

        return f"""Search your knowledge for specifications of {manufacturer} {model}.

ALREADY FOUND:
{current_values}

NEED TO FIND (search web knowledge for these):
{missing_fields}
{pv_module_guidance}

SEARCH STRATEGY:
1. Look for TECHNICAL DATASHEETS (PDFs, spec sheets, tech docs)
2. Check manufacturer official sites (NOT product pages with "Buy Now")
3. Search energy databases, certification sites, repositories
4. Check installation guides and technical manuals

⚠️ SOURCE QUALITY RULES:
- PREFER: Manufacturer datasheets, PDF spec sheets, technical docs
- AVOID: Product pages, pricing pages, review sites, marketing content
- AVOID: If you see "Buy Now", "Add to Cart", pricing → WRONG SOURCE, skip it
- Only datasheet/spec pages have accurate technical values

EXTRACTION QUALITY RULES:
- Preserve UNITS in responses: "5.76 kW" not just "5.76"
- DO NOT merge adjacent table cells - each cell is separate data
- If table has multiple columns (e.g., 50Hz / 60Hz), take FIRST value only
- Confirm model number matches EXACTLY: {model}
- Values must be realistic (not hallucinated)
- If value seems wrong (like wattage=9), look for better source

COMMON TABLE PARSING ERRORS TO AVOID:
    ❌ WRONG: Taking "10000/500" as single value → extract as {{"value": 10000}} only
  ❌ WRONG: Merging "0.775 / 1.7" from dual columns → extract first: 0.775
  ❌ WRONG: Guessing from marketing text → only use technical specs
  ✅ RIGHT: Take first column value from dual-column specs: 10000 (not 500)
  ✅ RIGHT: Each cell is independent - don't merge: Voltage=48V, Current=100A (separate)

Return JSON with found values AND UNITS:
{{"field_name": "value with unit" or numeric_value}}

Examples:
  {{"wattage_w": 550, "voc_v": 49.6, "temperature_coefficient_pmax": "-0.27%"}}
  {{"nominal_ac_power_output": "7.6 kW", "max_input_voltage": "480 V"}}

Return empty {{}} if you find nothing new.
Never guess - only return what you find."""

    # ========== PASS 3: Intelligent Filling of Remaining Nulls ==========

    @staticmethod
    def build_pass3_verification_prompt(
        manufacturer: str,
        model: str,
        extracted: dict,
        still_missing: list,
        schema_template: dict
    ) -> str:
        """PASS 3: Use already-found values to intelligently fill remaining nulls"""
        
        found_values = "\n".join([
            f"  {k}: {v}" for k, v in extracted.items() 
            if v and str(v).strip() != "" and v != "Not available"
        ]) or "  (none from PASS 1 & 2)"

        missing_fields = "\n".join([
            f"  - {field}" for field in still_missing
        ])

        return f"""Using ALREADY FOUND values, intelligently complete missing specs for {manufacturer} {model}.

KNOWN VALUES (from PDF + Web Search):
{found_values}

STILL MISSING (try to fill these):
{missing_fields}

INTELLIGENCE RULES:
1. Use relationships between specs you already have
2. Example: If you have Voc=49.6V and Isc=13.8A, infer general power class
3. Example: If you have efficiency=22%, infer typical wattage range
4. Use industry standards for equipment of this type
5. Apply electrical engineering knowledge to fill related fields

CRITICAL:
- Only fill if CONFIDENT (>90% sure)
- Use the values you already found as anchors
- Do NOT search web - use only reasoning
- If still unsure, leave field out

Return JSON with new found values:
{{"field_name": value}}

Return empty {{}} if you cannot determine anything new."""

    # ========== Utility: Build Alias Guide ==========

    @staticmethod
    def build_alias_guide(schema_template: dict) -> dict:
        """
        Build field alias guide for Gemini to watch for alternate names.
        
        Example:
            "max_power": ["Peak Power", "Max Power", "Pmax", "Maximum Power Output"]
        """
        aliases = {}
        for field, config in schema_template.items():
            # Skip if config is None or not a dict
            if config is None or not isinstance(config, dict):
                continue
            field_aliases = config.get("aliases", [])
            if field_aliases:
                aliases[field] = field_aliases

        return aliases
