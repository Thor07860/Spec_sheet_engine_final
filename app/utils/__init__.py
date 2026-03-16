# ==============================================================================
# utils/__init__.py
# ------------------------------------------------------------------------------
# Central export point for all utility classes.
#
# HOW TO USE:
#   from app.utils import WebScraper
#
# NOTE ABOUT REMOVED UTILITIES:
#   - PDFParser: Kept for future use, not imported (Gemini reads PDFs directly)
#   - TextCleaner: Kept for future use, not imported (text cleaning moved upstream)
#
# HOW TO ADD A NEW UTILITY IN THE FUTURE:
#   1. Create utils/new_util.py
#   2. Add import below
#   3. Add to __all__
# ==============================================================================

from app.utils.web_scraper import WebScraper

__all__ = [
    "WebScraper",
]