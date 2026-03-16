# ==============================================================================
# services/equipment_service.py
# ==============================================================================
# PURPOSE
#   Main orchestrator for the full equipment extraction pipeline.
#
# UPDATED PIPELINE
#   Cache → DB → Template → Search(optional) → Try PDF/Webpage →
#   Gemini extraction (PDF if available, grounded web fallback otherwise) →
#   Validation → Save
# ==============================================================================

import logging
import time
import re
from typing import Optional
from urllib.parse import urlparse

import requests
from sqlalchemy.orm import Session

from app.core.redis import redis_client

from app.repositories import (
    EquipmentRepository,
    JobRepository,
    SourceRepository,
    TemplateRepository,
    LogRepository,
)

# Lazy import SerperService (takes 6+ seconds to load, only needed when searching)
from app.services.extraction import ExtractionService
from app.services.matching_service import MatchingService
from app.services.validation import ValidationService
from app.services.s3_service import S3Service

from app.utils.web_scraper import WebScraper

from app.models.equipment_model import JobStatus, EquipmentCategory

logger = logging.getLogger(__name__)


class EquipmentService:
    def __init__(self, db: Session):
        self.db = db
        self._serper = None  # Lazy-loaded on first use
        self._s3 = None      # Lazy-loaded S3 service

        # repositories
        self.equipment_repo = EquipmentRepository(db)
        self.job_repo = JobRepository(db)
        self.source_repo = SourceRepository(db)
        self.template_repo = TemplateRepository(db)
        self.log_repo = LogRepository(db)

        # services
        self.extractor = ExtractionService()
        self.matcher = MatchingService()
        self.validator = ValidationService()

        # utilities
        self.web_scraper = WebScraper()

    @property
    def serper(self):
        """Lazy-load SerperService on first use (it takes ~6 seconds to import)"""
        if self._serper is None:
            from app.services.serper_service import SerperService
            logger.info("🔍 Lazy-loading SerperService (may take a moment)...")
            self._serper = SerperService(self.db)
        return self._serper

    @property
    def s3(self):
        """Lazy-load S3Service on first use (optional AWS configuration)"""
        if self._s3 is None:
            try:
                logger.info("🪣 Lazy-loading S3Service...")
                self._s3 = S3Service()
            except Exception as e:
                logger.warning("S3Service unavailable (optional feature): %s", str(e))
                self._s3 = False  # Mark as unavailable
        return self._s3 if self._s3 is not False else None

    # --------------------------------------------------------------------------
    # MAIN ENTRYPOINT
    # --------------------------------------------------------------------------
    def get_equipment_specs(
        self,
        manufacturer: str,
        model: str,
        equipment_type: str,
        equipment_sub_type: str
    ) -> dict:
        logger.info(
            "Equipment request: %s %s (%s/%s)",
            manufacturer,
            model,
            equipment_type,
            equipment_sub_type
        )

        request_start = time.time()
        existing_to_refresh = None

        # ------------------------------------------------------------------
        # STEP 1: CACHE
        # ------------------------------------------------------------------
        cached = redis_client.get(manufacturer, model)

        if cached:
            logger.info("Cache HIT for %s %s", manufacturer, model)
            return {
                "status": "success",
                "source": "cache",
                "data": cached,
                "job_id": None,
                "error": None,
                "metrics": None
            }

        # ------------------------------------------------------------------
        # STEP 2: DATABASE
        # ------------------------------------------------------------------
        existing = self.equipment_repo.get_by_manufacturer_model(
            manufacturer,
            model
        )

        if existing:
            if self._should_refresh_existing(existing, model, equipment_sub_type):
                logger.warning(
                    "DB HIT is stale/suspicious for %s %s; forcing fresh extraction",
                    manufacturer,
                    model
                )
                existing_to_refresh = existing
            else:
                logger.info("DB HIT for %s %s", manufacturer, model)

                data = self._serialize_equipment(existing)
                redis_client.set(manufacturer, model, data)

                return {
                    "status": "success",
                    "source": "database",
                    "data": data,
                    "job_id": None,
                    "error": None,
                    "metrics": None
                }

        # ------------------------------------------------------------------
        # STEP 3: CREATE JOB
        # ------------------------------------------------------------------
        job = self.job_repo.create(
            manufacturer=manufacturer,
            model=model,
            equipment_type=equipment_type,
            equipment_sub_type=equipment_sub_type
        )

        job_id = job.id
        logger.info("Created job %s", job_id)

        self.job_repo.update_status(job_id, JobStatus.PROGRESSING)

        # ------------------------------------------------------------------
        # STEP 4: TEMPLATE (PART 4: With fuzzy matching fallback)
        # ------------------------------------------------------------------
        template = self.template_repo.get_by_sub_type(equipment_sub_type)

        # PART 4 ENHANCEMENT: Fuzzy matching fallback for unknown sub_types
        if not template:
            logger.warning(
                "No exact match for equipment_sub_type=%s, trying fuzzy matching...",
                equipment_sub_type
            )
            # Try fuzzy matching against all available templates
            template = self._fuzzy_match_template(equipment_sub_type)
        
        if not template:
            error_msg = f"No template found for: {equipment_sub_type}"
            self.job_repo.update_status(
                job_id,
                JobStatus.FAILED,
                error_message=error_msg
            )
            return self._fail(job_id, error_msg)

        schema_template = template.schema_template

        # ------------------------------------------------------------------
        # STEP 5: SEARCH (OPTIONAL NOW)
        # ------------------------------------------------------------------
        search_results = []
        try:
            search_results = self.serper.search_spec_sheet(
                manufacturer=manufacturer,
                model=model,
                equipment_type=equipment_type
            ) or []

            logger.info(
                "Search returned %d candidate sources for %s %s",
                len(search_results),
                manufacturer,
                model
            )

        except Exception as e:
            logger.warning(
                "Source search failed for %s %s: %s",
                manufacturer,
                model,
                str(e)
            )
            search_results = []

        # Save discovered sources if any
        if search_results:
            try:
                self.source_repo.bulk_create(job_id=job_id, sources=search_results)
            except Exception as e:
                logger.warning("Failed to save source list for job %s: %s", job_id, str(e))

        # ------------------------------------------------------------------
        # STEP 6: FETCH DOCUMENT (BEST-EFFORT)
        # ------------------------------------------------------------------
        pdf_bytes: Optional[bytes] = None
        raw_text: Optional[str] = None
        best_url: Optional[str] = None
        original_url: Optional[str] = None

        for source in search_results:
            url = source.get("url")
            if not url:
                continue

            try:
                if self._is_pdf_url(url):
                    logger.info("Trying PDF download: %s", url)
                    response = requests.get(url, timeout=20)

                    if response.status_code == 200 and response.content:
                        pdf_bytes = response.content
                        best_url = url
                        original_url = url  # Store original URL before potential S3 upload
                        logger.info("Selected PDF source: %s", url)
                        
                        # ===================================================
                        # UPLOAD PDF TO S3 (PER-ITEM)
                        # ===================================================
                        if self.s3:
                            try:
                                s3_url = self.s3.upload_pdf_from_bytes(
                                    pdf_bytes=pdf_bytes,
                                    manufacturer=manufacturer,
                                    model=model,
                                    equipment_type=equipment_type
                                )
                                
                                if s3_url:
                                    best_url = s3_url  # Update best_url to S3 URL
                                    logger.info("📤 PDF uploaded to S3: %s", s3_url)
                                else:
                                    logger.warning("S3 upload failed, continuing with original URL: %s", url)
                                    
                            except Exception as e:
                                logger.warning("S3 upload error (non-fatal): %s", str(e))
                                # Continue with original URL if S3 fails
                        
                        break

                    logger.warning(
                        "PDF download failed for %s with status %s",
                        url,
                        response.status_code
                    )

                else:
                    logger.info("Trying webpage extraction: %s", url)
                    text = self.web_scraper.extract_text(url)

                    if text and len(text.strip()) > 500:
                        raw_text = text
                        best_url = url
                        original_url = url  # Store original URL
                        logger.info("Selected webpage source: %s", url)
                        break

            except Exception as e:
                logger.warning("Source failed %s: %s", url, str(e))

        # Mark selected source if any
        if best_url:
            try:
                self.source_repo.mark_selected(job_id=job_id, url=best_url)
            except Exception as e:
                logger.warning("Failed to mark selected source for job %s: %s", job_id, str(e))

        # ------------------------------------------------------------------
        # STEP 7: MODEL MATCHING (ONLY IF WEBPAGE TEXT AVAILABLE)
        # ------------------------------------------------------------------
        final_model = model

        if raw_text:
            try:
                candidates = self.matcher.extract_model_candidates_from_text(raw_text)
                match_result = self.matcher.find_best_match(model, candidates)

                final_model = self._resolve_final_model(
                    requested_model=model,
                    matched_model=match_result.get("matched_model"),
                    equipment_sub_type=equipment_sub_type
                )
            except Exception as e:
                logger.warning(
                    "Model matching failed for %s %s: %s",
                    manufacturer,
                    model,
                    str(e)
                )
                final_model = model

        self.job_repo.update_status(
            job_id,
            JobStatus.PROGRESSING,
            matched_model=final_model,
            selected_source_url=best_url
        )

        # ------------------------------------------------------------------
        # STEP 8: GEMINI EXTRACTION
        # ------------------------------------------------------------------
        # Cases:
        # 1. If PDF exists -> PDF extraction (PASS 1-4)
        # 2. If no PDF exists -> extractor will skip PASS 1-3 and use PASS 4 grounded fallback
        extraction_metrics = None
        extraction_error = None
        try:
            if pdf_bytes:
                logger.info(
                    "Starting PDF-backed extraction for %s %s",
                    manufacturer,
                    final_model
                )
            else:
                logger.info(
                    "No PDF available for %s %s; using grounded web fallback path.",
                    manufacturer,
                    final_model
                )

            raw_extracted, extraction_metrics = self.extractor.extract(
                pdf_bytes=pdf_bytes,
                schema_template=schema_template,
                manufacturer=manufacturer,
                model=final_model,
                equipment_sub_type=equipment_sub_type,
                source_url=best_url,
                enable_repair=True
            )

        except Exception as e:
            extraction_error = str(e)
            error_detail = f"{type(e).__name__}: {extraction_error}"
            logger.exception(
                "Extraction pipeline crashed for %s %s: %s",
                manufacturer,
                final_model,
                error_detail
            )
            raw_extracted = None

        if raw_extracted is None:
            error_msg = "Gemini extraction failed"

            self.job_repo.update_status(
                job_id,
                JobStatus.FAILED,
                error_message=error_msg
            )

            return self._fail(job_id, error_msg, metrics={"error_detail": extraction_error or "Unknown"})

        # ------------------------------------------------------------------
        # STEP 9: VALIDATION
        # ------------------------------------------------------------------
        validation = self.validator.validate(
            raw_data=raw_extracted,
            schema_template=schema_template,
            equipment_sub_type=equipment_sub_type
        )

        if not validation.is_valid:
            if validation.fields_extracted > 0 and validation.cleaned_data is not None:
                logger.warning(
                    "Validation below threshold for %s %s, but returning partial data: %d/%d fields",
                    manufacturer,
                    final_model,
                    validation.fields_extracted,
                    validation.fields_expected
                )
            else:
                error_msg = f"Validation failed: {'; '.join(validation.errors)}"

                self.job_repo.update_status(
                    job_id,
                    JobStatus.FAILED,
                    error_message=error_msg
                )

                return self._fail(job_id, error_msg)

        # Ensure no nulls in validated data
        final_metadata = self.extractor.helpers.fill_nulls_with_defaults(
            validation.cleaned_data or {},
            schema_template
        )

        # Repair obvious under-scaled inverter wattage values (e.g., 9 instead of 10000).
        final_metadata = self._repair_underscaled_inverter_wattage(
            metadata=final_metadata,
            requested_model=model,
            equipment_sub_type=equipment_sub_type
        )
        
        # ------------------------------------------------------------------
        # STEP 10: SAVE
        # ------------------------------------------------------------------
        category = self._resolve_category(equipment_sub_type)

        equipment_data = {
            "label": f"{manufacturer} {final_model}",
            "category": category,
            "equipment_type": equipment_type,
            "equipment_sub_type": equipment_sub_type,
            "manufacturer": manufacturer,
            "model": final_model,
            "priority": self._resolve_priority(equipment_sub_type),
            "equipment_metadata": final_metadata,
            "original_source_url": original_url,  # Original URL where spec sheet was found
            "source_url": best_url,  # Current URL (may be S3)
            "confident_score": validation.confidence_score
        }

        if existing_to_refresh:
            equipment = self.equipment_repo.update_extracted(
                equipment_id=existing_to_refresh.id,
                data=equipment_data
            )
        else:
            equipment = self.equipment_repo.create(equipment_data)

        self.job_repo.update_status(
            job_id,
            JobStatus.COMPLETED,
            equipment_id=equipment.id
        )

        serialized = self._serialize_equipment(equipment)
        redis_client.set(manufacturer, model, serialized)

        total_ms = (time.time() - request_start) * 1000
        
        # Prepare comprehensive metrics
        metrics_response = {
            "total_request_ms": total_ms,
            "gemini_extraction_ms": extraction_metrics.get("elapsed_ms", 0) if extraction_metrics else 0,
            "gemini_tokens": extraction_metrics.get("total_tokens", 0) if extraction_metrics else 0,
            "gemini_input_tokens": extraction_metrics.get("input_tokens", 0) if extraction_metrics else 0,
            "gemini_output_tokens": extraction_metrics.get("output_tokens", 0) if extraction_metrics else 0,
            "confidence_score": extraction_metrics.get("confidence_score", 0) if extraction_metrics else 0,
            "extraction_rate_pct": extraction_metrics.get("extraction_rate_pct", 0) if extraction_metrics else 0,
            "filled_fields": extraction_metrics.get("filled_fields", 0) if extraction_metrics else 0,
        }
        
        # Log comprehensive metrics
        logger.info(
            "━" * 80
        )
        logger.info(
            "✅ EXTRACTION COMPLETE: %s %s",
            manufacturer,
            final_model
        )
        logger.info(
            "📊 Extraction Rate: %.1f%% | Confidence: %.2f | Fields: %d filled",
            metrics_response["extraction_rate_pct"],
            metrics_response["confidence_score"],
            metrics_response["filled_fields"]
        )
        logger.info(
            "⏱️  Time: %.0fms total | %.0fms Gemini extraction",
            total_ms,
            metrics_response["gemini_extraction_ms"]
        )
        logger.info(
            "🔢 Tokens: %d total (input: %d | output: %d)",
            metrics_response["gemini_tokens"],
            metrics_response["gemini_input_tokens"],
            metrics_response["gemini_output_tokens"]
        )
        logger.info(
            "━" * 80
        )

        return {
            "status": "success",
            "source": "extracted",
            "data": serialized
        }

    def _is_pdf_url(self, url: str) -> bool:
        try:
            return urlparse(url).path.lower().endswith(".pdf")
        except Exception:
            return url.lower().endswith(".pdf")

    # --------------------------------------------------------------------------
    # FAIL RESPONSE
    # --------------------------------------------------------------------------
    def _fail(self, job_id, error_msg: str, metrics=None) -> dict:
        total_ms = 0
        if metrics:
            total_ms = metrics.get("elapsed_ms", 0)
        
        return {
            "status": "failed",
            "source": None,
            "data": None,
            "job_id": str(job_id),
            "error": error_msg
        }

    # --------------------------------------------------------------------------
    # SERIALIZATION
    # --------------------------------------------------------------------------
    def _normalize_specifications(self, specs: dict) -> dict:
        """
        Clean and normalize extracted specification values.
        
        Rules:
        1. Remove extraction metadata fields (datasheet_source_type, etc)
        2. Convert string "True"/"False" to boolean True/False
        3. Extract numeric values from strings containing units
        4. Normalize dimension units (convert cm to mm where field is _mm)
        5. Handle dual values (e.g., "775/1.7" → use first value)
        """
        if not isinstance(specs, dict):
            return specs
        
        # Fields that are extraction metadata, not actual specs
        metadata_fields = {
            "datasheet_source_type",
            "extraction_method",
            "source_type",
            "data_origin",
            "extraction_confidence",
            "raw_text"
        }
        
        normalized = {}
        
        for key, value in specs.items():
            # Skip metadata fields
            if key in metadata_fields:
                continue
            
            if value is None:
                normalized[key] = None
                continue
            
            # Convert string "True"/"False" to actual booleans
            if isinstance(value, str):
                if value.lower() == "true":
                    normalized[key] = True
                    continue
                elif value.lower() == "false":
                    normalized[key] = False
                    continue
                
                # Handle dual values like "775/1.7" → take first value
                if "/" in value and key in ["weight_kg", "dimensions_mm"]:
                    first_val = value.split("/")[0].strip()
                    value = first_val
                
                # For _mm fields: convert cm to mm if needed
                if key.endswith("_mm") and "cm" in value.lower():
                    # Extract numeric value
                    import re
                    numbers = re.findall(r"[\d.]+", value)
                    if numbers:
                        # Convert cm to mm (multiply by 10)
                        cm_val = float(numbers[0])
                        normalized[key] = f"{cm_val * 10:.1f} mm"
                        continue
                
                # Remove trailing units from values (already in field name)
                # e.g., "21 kg" → 21 for weight_kg
                if key.endswith(("_kg", "_w", "_v", "_a", "_hz", "_pct", "_c")):
                    import re
                    numbers = re.findall(r"^[\d.]+", value.strip())
                    if numbers:
                        try:
                            normalized[key] = float(numbers[0])
                            continue
                        except (ValueError, IndexError):
                            pass
                
                # For boolean-like fields, convert "Yes"/"No" to boolean
                if key in ["has_builtin_afci", "has_builtin_dc_disconnect", 
                           "has_builtin_rapid_shutdown", "is_rapid_shutdown_compliant",
                           "anodized", "is_aluminum", "rapid_shutdown_compliant",
                           "module_level_monitoring"]:
                    if value.lower() in ["yes", "true"]:
                        normalized[key] = True
                        continue
                    elif value.lower() in ["no", "false"]:
                        normalized[key] = False
                        continue
            
            normalized[key] = value
        
        return normalized

    def _serialize_equipment(self, equipment):
        # Clean specifications: remove duplicated identity fields
        specs = equipment.equipment_metadata or {}
        if isinstance(specs, dict):
            # Remove duplicated fields from specs since they're at top level
            cleaned_specs = {k: v for k, v in specs.items() 
                           if k not in ["manufacturer", "model", "equipment_type", "equipment_sub_type"]}
            # Normalize values
            cleaned_specs = self._normalize_specifications(cleaned_specs)
        else:
            cleaned_specs = specs

        # Only include source_document if at least one URL exists
        source_doc = None
        if equipment.original_source_url or equipment.source_url:
            source_doc = {
                "original_url": equipment.original_source_url,
                "processed_url": equipment.source_url
            }

        result = {
            "id": str(equipment.id),
            "label": equipment.label,
            "category": equipment.category.value if equipment.category else None,
            "equipment_type": equipment.equipment_type,
            "equipment_sub_type": equipment.equipment_sub_type,
            "manufacturer": equipment.manufacturer,
            "model": equipment.model,
            "specifications": cleaned_specs,
            "confidence": {
                "score": equipment.confident_score
            }
        }
        
        # Only add source_document if it has content
        if source_doc:
            result["source_document"] = source_doc
        
        return result

    # --------------------------------------------------------------------------
    # CATEGORY RESOLUTION
    # --------------------------------------------------------------------------
    def _resolve_category(self, equipment_sub_type: str) -> EquipmentCategory:
        category_map = {
            "pv_module": EquipmentCategory.SOURCE,
            "ac_module": EquipmentCategory.SOURCE,
            "string_inverter": EquipmentCategory.CONVERSION,
            "solaredge_inverter": EquipmentCategory.CONVERSION,
            "microinverter": EquipmentCategory.CONVERSION,
            "ess": EquipmentCategory.STORAGE,
        }

        return category_map.get(
            equipment_sub_type,
            EquipmentCategory.CONVERSION
        )

    # --------------------------------------------------------------------------
    # PRIORITY
    # --------------------------------------------------------------------------
    def _resolve_priority(self, equipment_sub_type: str) -> int:
        priority_map = {
            "pv_module": 10,
            "ac_module": 11,
            "string_inverter": 30,
            "solaredge_inverter": 31,
            "microinverter": 32,
            "ess": 55,
        }

        return priority_map.get(
            equipment_sub_type,
            100
        )

    # --------------------------------------------------------------------------
    # PART 4: FUZZY TEMPLATE MATCHING
    # --------------------------------------------------------------------------
    def _fuzzy_match_template(self, requested_sub_type: str):
        """
        PART 4 Enhancement: Fuzzy matching for unknown equipment_sub_types.
        Uses simple substring matching to find similar templates.
        
        Example: "solar_panel" -> "pv_module" (if "panel" matches "pv_module")
        
        Returns: Best matching template or None
        """
        try:
            from difflib import SequenceMatcher
            
            # Get all available templates
            all_templates = self.template_repo.get_all()  # Assuming get_all() exists
            
            if not all_templates:
                logger.warning("No templates available for fuzzy matching")
                return None
            
            # Simple fuzzy matching: find highest similarity ratio
            best_match = None
            best_ratio = 0.6  # Minimum 60% similarity threshold
            
            for template in all_templates:
                # Compare requested_sub_type with template's sub_type
                ratio = SequenceMatcher(
                    None,
                    requested_sub_type.lower(),
                    template.equipment_sub_type.lower()
                ).ratio()
                
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = template
                    logger.info(
                        "Fuzzy match: %s -> %s (%.0f%% similarity)",
                        requested_sub_type,
                        template.equipment_sub_type,
                        ratio * 100
                    )
            
            return best_match
        except Exception as e:
            logger.error("Fuzzy matching failed: %s", str(e))
            return None

    # --------------------------------------------------------------------------
    # RESOLVE FINAL MODEL
    # --------------------------------------------------------------------------
    def _resolve_final_model(
        self,
        requested_model: str,
        matched_model: Optional[str],
        equipment_sub_type: str
    ) -> str:
        """
        Determine which model name to use in the final equipment record.

        Priority:
        1. If fuzzy matching found a similar model -> use matched_model
        2. Otherwise -> use requested_model
        """
        if matched_model and matched_model.strip():
            generic_model_tokens = {
                "rail", "module", "panel", "inverter", "battery", "optimizer", "gateway"
            }
            cleaned_match = matched_model.strip()
            lowered_match = cleaned_match.lower()
            lowered_requested = requested_model.strip().lower()

            # Reject generic one-word matches that drop key model identity.
            if lowered_match in generic_model_tokens and lowered_match not in lowered_requested:
                logger.warning(
                    "Ignoring generic matched model '%s'; keeping requested '%s'",
                    matched_model,
                    requested_model
                )
                return requested_model

            # If requested model already contains the matched token (e.g., XR10 Rail),
            # keep the original request to avoid losing specificity.
            if lowered_match in lowered_requested and len(cleaned_match) < len(requested_model.strip()):
                logger.info(
                    "Matched model '%s' is less specific than requested '%s'; keeping requested",
                    matched_model,
                    requested_model
                )
                return requested_model

            logger.info(
                "Using fuzzy matched model: %s (original: %s)",
                matched_model,
                requested_model
            )
            return matched_model

        logger.info(
            "No fuzzy match found; using requested model: %s",
            requested_model
        )
        return requested_model

    def _should_refresh_existing(self, existing, requested_model: str, equipment_sub_type: str) -> bool:
        """Return True when an existing DB record appears stale or low-quality."""
        metadata = existing.equipment_metadata if isinstance(existing.equipment_metadata, dict) else {}

        existing_model = (existing.model or "").strip().lower()
        requested = (requested_model or "").strip().lower()
        generic_names = {"rail", "module", "panel", "inverter", "battery", "optimizer", "gateway"}

        if existing_model in generic_names and requested and existing_model != requested:
            return True

        # Catch obviously wrong inverter wattage values (e.g., 9 for a 10kW inverter).
        if equipment_sub_type == "string_inverter":
            raw_power = metadata.get("wattage_w")
            power_val = self._to_float(raw_power)
            if power_val is not None and power_val < 1000:
                return True

        # For IronRidge rails, prefer official IronRidge source URLs over distributor pages.
        if equipment_sub_type == "mounting_rail":
            mfr = (existing.manufacturer or "").lower()
            src = (existing.source_url or "").lower()
            if "ironridge" in mfr and src:
                is_official = ("files.ironridge.com" in src) or ("ironridge.com" in src)
                if not is_official:
                    return True

        return False

    def _to_float(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().lower().replace(",", "")
        if not text:
            return None
        num = []
        seen_dot = False
        for ch in text:
            if ch.isdigit():
                num.append(ch)
                continue
            if ch == "." and not seen_dot:
                num.append(ch)
                seen_dot = True
                continue
            if num:
                break
        if not num:
            return None
        try:
            return float("".join(num))
        except Exception:
            return None

    def _repair_underscaled_inverter_wattage(
        self,
        metadata: dict,
        requested_model: str,
        equipment_sub_type: str
    ) -> dict:
        """
        Fix known under-scaling issue where inverter power is returned as single digits
        even when model indicates kW class (e.g., "Primo 10.0-1" -> 10000 W).
        """
        if equipment_sub_type not in {"string_inverter", "solaredge_inverter"}:
            return metadata

        wattage = self._to_float(metadata.get("wattage_w"))
        if wattage is None or wattage >= 1000:
            return metadata

        model_text = (requested_model or "").strip()
        if not model_text:
            return metadata

        # Capture a likely kW class token from model names like:
        # "Primo 10.0-1", "SE7600H", "SE10000H", etc.
        kw_match = re.search(r"(\d{1,2}(?:\.\d)?)", model_text)
        if kw_match:
            try:
                kw_value = float(kw_match.group(1))
                if 1.0 <= kw_value <= 50.0:
                    repaired = int(round(kw_value * 1000))
                    metadata["wattage_w"] = repaired
                    logger.warning(
                        "Repaired under-scaled wattage_w from %s to %s using model '%s'",
                        wattage,
                        repaired,
                        requested_model
                    )
            except Exception:
                return metadata

        return metadata