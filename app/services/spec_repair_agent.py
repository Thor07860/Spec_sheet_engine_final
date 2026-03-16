# app/services/spec_repair_agent.py
# =============================================================================
# STUB: Multi-source spec repair agent
# Status: NOT YET IMPLEMENTED - Design complete, awaiting full implementation
# =============================================================================
# Purpose:
#   When extraction is partial (40-70% coverage), use this agent to:
#   1. Search for alternative sources
#   2. Extract from multiple datasheets
#   3. Compare and merge results
#   4. Return consensus with higher confidence
# =============================================================================

from app.services.serper_service import SerperService
from app.services.extraction import ExtractionService
from app.utils.web_scraper import WebScraper


class SpecRepairAgent:
    """
    Multi-source verification agent.
    Extracts specs from multiple sources and compares for consensus.
    Improves confidence when data matches across sources.
    """

    def __init__(self):
        self.serper = SerperService(db=None)  # Will be passed by caller
        self.extractor = ExtractionService()
        self.scraper = WebScraper()
        # PDFParser kept for future: from app.utils.pdf_parser import PDFParser

    def repair_missing_fields(
        self,
        manufacturer,
        model,
        equipment_sub_type,
        schema,
        current_metadata
    ):
        """
        Multi-source repair strategy.
        
        TODO: Implement full multi-source verification:
        1. Identify missing critical fields
        2. Search for additional datasheets
        3. Extract from each source
        4. Compare values
        5. Return consensus
        """

        missing_fields = [
            k for k, v in current_metadata.items() if v is None
        ]

        if not missing_fields:
            return {}

        # search trusted sources
        search_results = self.serper.search(
            f"{manufacturer} {model} datasheet pdf"
        )

        for result in search_results:

            url = result["link"]

            try:

                if url.endswith(".pdf"):
                    # Direct PDF reading via Gemini (preferred)
                    text = self.scraper.extract(url)  # Fallback to scraper
                else:
                    text = self.scraper.extract(url)

                repaired = self.extractor.extract_missing_fields(
                    text=text,
                    model=model,
                    fields=missing_fields,
                    schema=schema
                )

                if repaired:
                    return repaired

            except Exception:
                continue

        return {}