# ==============================================================================
# utils/web_scraper.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Fetches and extracts text content from webpages (product pages, spec pages).
#   Used when the spec source is a webpage rather than a PDF.
#
# WHY BEAUTIFULSOUP:
#   - Simple and reliable for static HTML pages
#   - Handles malformed HTML gracefully
#   - Much lighter than Playwright (no browser overhead)
#   - Most manufacturer spec pages are static HTML — no JS rendering needed
#
# WHAT THIS FILE DOES:
#   1. Downloads the webpage HTML
#   2. Removes noise (nav, footer, ads, scripts, styles)
#   3. Extracts only the meaningful text content
#   4. Returns clean raw text for the text_cleaner to process further
#
# RULE:
#   This file only handles webpage downloading and HTML parsing.
#   It does NOT clean spec text, call Gemini, or validate anything.
# ==============================================================================

import requests
import logging
from typing import Optional
from bs4 import BeautifulSoup  # HTML parsing library

logger = logging.getLogger(__name__)


class WebScraper:

    def __init__(self):
        # Request timeout for webpage downloads
        self.timeout = 20

        # Browser-like headers to avoid being blocked
        # WHY: Many manufacturer sites return 403 Forbidden without a User-Agent
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        # HTML tags that contain navigation, ads, or other noise
        # WHY: These tags never contain equipment specs — removing them
        # reduces noise for Gemini and saves tokens
        self.noise_tags = [
            "nav",          # navigation menus
            "header",       # page header (logo, nav)
            "footer",       # page footer (links, copyright)
            "aside",        # sidebars
            "script",       # JavaScript code
            "style",        # CSS styles
            "noscript",     # fallback content for no-JS browsers
            "iframe",       # embedded frames
            "form",         # contact forms, search boxes
            "button",       # UI buttons
            "svg",          # vector graphics
            "img",          # images (no text content)
            "video",        # video players
            "figure",       # image containers
        ]

        # CSS class name patterns that usually indicate non-spec content
        # WHY: Even within <div> tags, these classes signal noise content
        self.noise_class_patterns = [
            "cookie", "banner", "popup", "modal",
            "social", "share", "subscribe", "newsletter",
            "breadcrumb", "pagination", "related", "recommend"
        ]

    # --------------------------------------------------------------------------
    # extract_text()
    # --------------------------------------------------------------------------
    # Main entry point.
    # Downloads a webpage and returns its meaningful text content.
    #
    # Returns:
    #   str  → extracted text from the page
    #   None → if download or parsing fails
    # --------------------------------------------------------------------------
    def extract_text(self, url: str) -> Optional[str]:

        logger.info("Scraping webpage: %s", url)

        # Step 1: Download the HTML
        html = self._download_page(url)

        if html is None:
            return None

        # Step 2: Parse and extract clean text from HTML
        return self._extract_from_html(html, url)

    # --------------------------------------------------------------------------
    # _download_page()
    # --------------------------------------------------------------------------
    # Downloads webpage HTML.
    # Returns raw HTML string or None on failure.
    # --------------------------------------------------------------------------
    def _download_page(self, url: str) -> Optional[str]:

        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                # Follow redirects automatically
                # WHY: Manufacturer sites often redirect http → https
                allow_redirects=True
            )

            response.raise_for_status()

            # Detect encoding from response headers or content
            # WHY: Some pages use UTF-8, some use latin-1 — wrong encoding
            # causes garbled text in extracted specs
            response.encoding = response.apparent_encoding

            logger.info(
                "Downloaded webpage: %s (%.1f KB)",
                url, len(response.text) / 1024
            )

            return response.text

        except requests.Timeout:
            logger.error("Webpage download timed out: %s", url)
            return None

        except requests.HTTPError as e:
            logger.error("Webpage HTTP error %s: %s", str(e), url)
            return None

        except Exception as e:
            logger.error("Webpage download failed: %s — URL: %s", str(e), url)
            return None

    # --------------------------------------------------------------------------
    # _extract_from_html()
    # --------------------------------------------------------------------------
    # Parses HTML with BeautifulSoup and extracts meaningful text.
    #
    # STRATEGY:
    #   1. Parse HTML into a document tree
    #   2. Remove all noise tags (nav, footer, script, etc.)
    #   3. Remove elements with noise CSS classes
    #   4. Try to find the main content section first
    #      (manufacturers often use <main>, <article>, or id="content")
    #   5. Fall back to full body text if no main section found
    #   6. Extract clean text preserving line breaks
    # --------------------------------------------------------------------------
    def _extract_from_html(self, html: str, url: str) -> Optional[str]:

        try:
            # Parse HTML using the lxml parser (faster than html.parser)
            # WHY lxml: Much faster on large HTML pages, better handling of
            # malformed HTML which is common on older manufacturer sites
            soup = BeautifulSoup(html, "lxml")

            # --- Step 1: Remove noise tags completely ---
            for tag_name in self.noise_tags:
                for tag in soup.find_all(tag_name):
                    tag.decompose()     # removes tag and all its children from tree

            # --- Step 2: Remove elements with noise CSS classes ---
            for pattern in self.noise_class_patterns:
                for tag in soup.find_all(
                    class_=lambda c: c and pattern in " ".join(c).lower()
                ):
                    tag.decompose()

            # --- Step 3: Try to find the main content area ---
            # Manufacturers often put specs in a clearly identified section
            main_content = (
                soup.find("main") or                        # HTML5 main tag
                soup.find("article") or                     # article tag
                soup.find(id="content") or                  # common id="content"
                soup.find(id="main-content") or             # common id="main-content"
                soup.find(id="product-details") or          # product detail pages
                soup.find(class_="specifications") or       # spec section
                soup.find(class_="product-specs") or        # product spec section
                soup.find(class_="technical-specs") or      # technical specs section
                soup.find(class_="datasheet")               # datasheet section
            )

            # Use main content if found, fall back to full body
            target = main_content if main_content else soup.find("body")

            if not target:
                logger.warning("No content found on page: %s", url)
                return None

            # --- Step 4: Extract text with separator ---
            # get_text(separator="\n") puts a newline between each element
            # WHY: Prevents "Model: SE7600HMax Power: 7600W" (words joined together)
            # strip=True removes leading/trailing whitespace from each element
            text = target.get_text(separator="\n", strip=True)

            # Remove excessive blank lines (more than 2 consecutive newlines)
            import re
            text = re.sub(r"\n{3,}", "\n\n", text)

            if not text.strip():
                logger.warning("Empty text extracted from: %s", url)
                return None

            logger.info(
                "Extracted %d chars from webpage: %s",
                len(text), url
            )

            return text

        except Exception as e:
            logger.error("HTML parsing failed for %s: %s", url, str(e))
            return None