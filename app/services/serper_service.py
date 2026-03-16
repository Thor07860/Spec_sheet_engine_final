# ==============================================================================
# services/serper_service.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Handles all Google search operations using the Serper API.
#
# KEY FIX IN THIS VERSION:
#   Now runs UP TO 4 SEARCHES instead of 2:
#   1. PDF search on manufacturer site (highest quality)
#   2. PDF search anywhere on web (broader)
#   3. Open repository search (manualslib, energysage, etc — never block)
#   4. General spec page search (fallback)
#
#   This ensures Tesla, Enphase, and other blocked sites still work
#   because we find their specs on open repositories instead.
# ==============================================================================

import requests
import logging
import re
from urllib.parse import urlparse
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.trusted_source_repository import TrustedSourceRepository

logger = logging.getLogger(__name__)


class SerperService:

    def __init__(self, db: Session):
        self.db = db
        self.trusted_repo = TrustedSourceRepository(db)
        self.api_key = settings.SERPER_API_KEY
        self.base_url = settings.SERPER_BASE_URL
        self.max_results = settings.SERPER_MAX_RESULTS

        # ==============================================================
        # OPEN REPOSITORIES — these sites NEVER block automated access
        # and always have spec sheets for major US solar equipment.
        # We explicitly search these when manufacturer site is blocked.
        # ==============================================================
        self.open_repositories = [
            "manualslib.com",
            "energysage.com",
            "gogreensolar.com",
            "wholesalesolar.com",
            "altestore.com",
            "solar-electric.com",
            "solarreviews.com",
            "datasheets.com",
        ]

    # --------------------------------------------------------------------------
    # search_spec_sheet()
    # --------------------------------------------------------------------------
    # Runs multiple search strategies and returns ranked trusted results.
    #
    # SEARCH STRATEGY (in order of priority):
    #   1. PDF on manufacturer's own site  → best quality, sometimes blocked
    #   2. PDF anywhere on web             → broader, finds mirrors
    #   3. Open repository search          → never blocked, always works
    #   4. General spec page               → last resort fallback
    # --------------------------------------------------------------------------
    def search_spec_sheet(
        self,
        manufacturer: str,
        model: str,
        equipment_type: str
    ) -> List[dict]:

        logger.info(
            "Searching spec sheet: manufacturer=%s model=%s type=%s",
            manufacturer, model, equipment_type
        )

        all_results = []
        seen_urls = set()

        manufacturer_domain = self._get_manufacturer_domain(manufacturer)

        # ------------------------------------------------------------------
        # IRONRIDGE PRIORITY: probe official cut-sheet URLs first
        # ------------------------------------------------------------------
        if "ironridge" in manufacturer.lower():
            official_urls = self._build_ironridge_candidate_urls(model)
            for url in official_urls:
                if self._probe_pdf_url(url):
                    self._merge_results(
                        all_results,
                        seen_urls,
                        [{
                            "url": url,
                            "domain": self._extract_domain(url),
                            "title": f"IronRidge official cut sheet {model}",
                            "snippet": "Official IronRidge cut sheet",
                            "source_type": "pdf",
                            "trust_score": 0,
                        }]
                    )
                    logger.info("IronRidge official URL matched: %s", url)

            # Dedicated site search on files.ironridge.com (official docs host)
            query0 = f"{manufacturer} {model} cut sheet filetype:pdf site:files.ironridge.com"
            results0 = self._call_serper(query0)
            self._merge_results(all_results, seen_urls, results0)
            logger.info("Search 0 (IronRidge official files host): %d results", len(results0))

        # ------------------------------------------------------------------
        # SEARCH 1: PDF on manufacturer's own site
        # Best quality — official datasheet from the source
        # ------------------------------------------------------------------
        if manufacturer_domain:
            query1 = (
                f"{manufacturer} {model} datasheet filetype:pdf "
                f"site:{manufacturer_domain}"
            )
            results1 = self._call_serper(query1)
            self._merge_results(all_results, seen_urls, results1)
            logger.info("Search 1 (manufacturer PDF): %d results", len(results1))

        # ------------------------------------------------------------------
        # SEARCH 2: PDF anywhere on the web
        # Finds PDFs hosted on distributors, repositories, mirrors
        # This is the key fallback when manufacturer site blocks us
        # ------------------------------------------------------------------
        query2 = (
            f"{manufacturer} {model} {equipment_type} "
            f"datasheet specifications filetype:pdf"
        )
        results2 = self._call_serper(query2)
        self._merge_results(all_results, seen_urls, results2)
        logger.info("Search 2 (web PDF): %d results", len(results2))

        # ------------------------------------------------------------------
        # SEARCH 3: Open repository search
        # These sites never block — guaranteed to return accessible content
        # WHY: Tesla, some Enphase pages block bots but manualslib doesn't
        # ------------------------------------------------------------------
        repo_sites = " OR site:".join(self.open_repositories)
        query3 = (
            f"{manufacturer} {model} {equipment_type} specifications "
            f"site:{repo_sites}"
        )
        results3 = self._call_serper(query3)
        self._merge_results(all_results, seen_urls, results3)
        logger.info("Search 3 (open repositories): %d results", len(results3))

        # ------------------------------------------------------------------
        # SEARCH 4: General spec page (last resort)
        # Catches product pages, web-based spec sheets
        # ------------------------------------------------------------------
        query4 = (
            f"{manufacturer} {model} {equipment_type} "
            f"technical specifications"
        )
        results4 = self._call_serper(query4)
        self._merge_results(all_results, seen_urls, results4)
        logger.info("Search 4 (general): %d results", len(results4))

        # PART 1 ENHANCEMENT: Aggressive PDF filtering
        # Separate PDFs from web pages and prioritize PDFs first
        pdf_results = [r for r in all_results if r.get("source_type") == "pdf" or r["url"].lower().endswith(".pdf")]
        web_results = [r for r in all_results if r.get("source_type") != "pdf" and not r["url"].lower().endswith(".pdf")]
        
        # PART 2: Assess source quality and filter low-quality sources
        # Rejects marketing pages, blogs, review sites as primary sources
        pdf_results = self._assess_source_quality(pdf_results)
        web_results = self._assess_source_quality(web_results)
        
        # Score all results against trusted sources table
        scored_pdf_results = self._score_results(pdf_results)
        scored_web_results = self._score_results(web_results)
        
        # Filter PDFs by trust score (primary results)
        trusted_pdfs = [
            r for r in scored_pdf_results
            if r["trust_score"] >= settings.MIN_TRUST_SCORE
        ]
        
        # Filter web results by trust score (fallback)
        trusted_web = [
            r for r in scored_web_results
            if r["trust_score"] >= settings.MIN_TRUST_SCORE
        ]
        
        # Sort: PDFs first (highest trust), then web pages
        # WHY: PDF > webpage for extraction quality
        trusted_pdfs.sort(key=lambda x: x["trust_score"], reverse=True)
        trusted_web.sort(key=lambda x: x["trust_score"], reverse=True)
        
        # Combine: PDFs first, then web pages
        trusted_results = trusted_pdfs + trusted_web

        logger.info(
            "Found %d trusted results for %s %s",
            len(trusted_results), manufacturer, model
        )

        # Log top 3 sources for debugging
        for i, r in enumerate(trusted_results[:3]):
            logger.info(
                "  Source %d: %s (trust=%d, type=%s)",
                i + 1, r["url"], r["trust_score"], r["source_type"]
            )

        return trusted_results

    # --------------------------------------------------------------------------
    # search()
    # --------------------------------------------------------------------------
    # PASS 4: General web search for internet search extraction (no PDF filter).
    # Used when PDFs are unavailable to extract specs from web pages.
    # 
    # Args:
    #   query: Search query string (e.g., "Tesla Powerwall 2 specifications")
    #
    # Returns:
    #   dict with 'organic' key containing list of search results
    # --------------------------------------------------------------------------
    def search(self, query: str) -> dict:
        """
        General web search for PASS 4 internet extraction.
        Searches the web for product specifications without filtering for PDFs.
        """
        logger.info("General web search: %s", query)
        
        # Call Serper API with the provided query
        results = self._call_serper(query)
        
        if results:
            logger.info("Found %d web results", len(results))
        else:
            logger.warning("No web results found for query: %s", query)
        
        # Return in the same format as Serper API
        return {
            "organic": results,
            "searchParameters": {
                "q": query
            }
        }

    # --------------------------------------------------------------------------
    # _merge_results()
    # --------------------------------------------------------------------------
    # Adds new results to the main list, skipping duplicates.
    # --------------------------------------------------------------------------
    def _merge_results(
        self,
        all_results: List[dict],
        seen_urls: set,
        new_results: List[dict]
    ):
        for result in new_results:
            url = result["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                all_results.append(result)

    # --------------------------------------------------------------------------
    # _call_serper()
    # --------------------------------------------------------------------------
    # Makes the actual HTTP request to the Serper API.
    # --------------------------------------------------------------------------
    def _call_serper(self, query: str) -> List[dict]:

        logger.debug("Serper query: %s", query)

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "q": query,
            "num": self.max_results,
            "gl": "us",     # US results only
            "hl": "en"      # English language
        }

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=10
            )

            response.raise_for_status()
            data = response.json()
            organic_results = data.get("organic", [])

            results = []
            for item in organic_results:
                url = item.get("link", "")
                if not url:
                    continue

                domain = self._extract_domain(url)
                source_type = "pdf" if self._is_pdf_url(url) else "webpage"

                results.append({
                    "url": url,
                    "domain": domain,
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "source_type": source_type,
                    "trust_score": 0    # filled by _score_results()
                })

            return results

        except requests.Timeout:
            logger.error("Serper API timeout for query: %s", query)
            return []

        except requests.HTTPError as e:
            logger.error("Serper API HTTP error: %s", str(e))
            return []

        except Exception as e:
            logger.error("Serper API error: %s", str(e))
            return []

    # --------------------------------------------------------------------------
    # _score_results()
    # --------------------------------------------------------------------------
    # Looks up trust score for each result's domain from trusted_sources table.
    # Adds source priority scoring:
    # - PDF datasheets from manufacturer: highest priority
    # - PDFs from distributors/repos: high priority
    # - Webpage from manufacturer: medium priority
    # - Webpage from distributors: lower priority
    # --------------------------------------------------------------------------
    def _score_results(self, results: List[dict]) -> List[dict]:

        for result in results:
            domain = result.get("domain", "")
            trusted = self.trusted_repo.get_by_domain(domain)

            if trusted:
                result["trust_score"] = trusted.trust_score
                result["source_type_category"] = trusted.source_type
            else:
                result["trust_score"] = 0

            # Apply source type bonus for ranking
            # PDF datasheets get priority boost
            source_type = result.get("source_type", "webpage")
            source_category = result.get("source_type_category", "")

            # Boost PDF from manufacturer or repository
            if source_type == "pdf":
                if source_category in ["manufacturer", "repository", "distributor"]:
                    result["trust_score"] += 50  # Major boost for trusted PDFs
                else:
                    result["trust_score"] += 25  # Minor boost for any PDF

            # Explicit domain boosts for official doc hosts.
            if domain == "files.ironridge.com":
                result["trust_score"] += 120
            elif domain == "ironridge.com" or domain.endswith(".ironridge.com"):
                result["trust_score"] += 80

            logger.debug(
                "Source ranking: %s (domain=%s, type=%s, category=%s, score=%d)",
                result.get("url", "")[:60],
                domain,
                source_type,
                source_category,
                result["trust_score"]
            )

        return results

    # --------------------------------------------------------------------------
    # _assess_source_quality()
    # --------------------------------------------------------------------------
    # Filters results by source quality, rejecting marketing/blog pages.
    #
    # QUALITY TIERS:
    #   TIER 1 (Excellent): PDF + manufacturer domain
    #   TIER 2 (Good): PDF + known repository
    #   TIER 3 (Fair): Spec page (technical, not marketing)
    #   TIER 4 (Poor): Marketing page, blog, review site
    #   REJECTION: energysage.com product pages, solarreviews.com reviews, etc
    # --------------------------------------------------------------------------
    def _assess_source_quality(self, results: List[dict]) -> List[dict]:
        """
        Filter results by source quality. Reject marketing pages, prioritize datasheets.
        
        REJECT SITES (marketing/review only, no technical specs):
          - energysage.com (pricing comparison, reviews, not specs)
          - solarreviews.com (product reviews, not technical specs)
          - solarpowerhome.com (marketing content)
          - blog pages and forums
          - product pages (/product/, /shop/, /buy/, /store/)
        
        ACCEPT SITES (in priority order):
          - PDFs (datasheets, spec sheets - highest quality)
          - Manufacturer domains (.com, .de, .fr for that brand)
          - Datasheet repositories (manualslib, datasheets.com, etc)
          - Distributor spec sheets (if not product/shop pages)
          - Government/standards docs
        """
        
        # Marketing sites - REJECT as primary source (web pages only)
        reject_domains_strict = {
            "energysage.com",
            "solarreviews.com",
            "solarpowerhome.com",
            "solarpanelsplus.com",
            "influenergy.com",
            "letsbuild.com",
            "news.ycombinator.com",
            "reddit.com",  # User discussions, not specs
        }
        
        # Blog/review/product page indicators - REJECT these URL patterns
        reject_patterns = [
            "/blog/",
            "/review",
            "/reviews",
            "/forum",
            "/thread",
            "/post/",
            "/product/",
            "/shop/",
            "/buy/",
            "/store/",
            "/order",
            "/cart",
            "?product=",
            "?id=",
        ]
        
        # GOOD patterns to prioritize
        good_patterns = [
            "/datasheet",
            "/specification",
            "/spec-sheet",
            "/technical",
            "/download",
            "datasheet",
            "specification",
            "technical-data",
            "filetype:pdf",
        ]
        
        filtered = []
        
        for result in results:
            url = result.get("url", "").lower()
            domain = result.get("domain", "").lower()
            source_type = result.get("source_type", "")
            title = result.get("title", "").lower()
            
            # PRIORITY 1: PDFs are always accepted (highest quality)
            # because PDF implies structured technical content (datasheet)
            if source_type == "pdf" or url.endswith(".pdf"):
                result["quality_tier"] = "tier_1_pdf"
                filtered.append(result)
                continue
            
            # PRIORITY 2: Reject strict marketing sites (web pages only)
            if domain in reject_domains_strict:
                logger.debug(
                    "REJECTED (marketing site): %s from %s",
                    url[:60], domain
                )
                continue
            
            # PRIORITY 3: Reject product pages and shopping
            is_product_page = any(pattern in url for pattern in reject_patterns)
            if is_product_page:
                logger.debug(
                    "REJECTED (product/shop page): %s",
                    url[:60]
                )
                continue
            
            # PRIORITY 4: Reject blog/forum pages
            is_blog = "/blog/" in url or "/forum" in url or "/thread" in url
            if is_blog:
                logger.debug(
                    "REJECTED (blog/forum): %s",
                    url[:60]
                )
                continue
            
            # PRIORITY 5: Datasheet pages are good
            is_datasheet = any(pattern in (url + " " + title) for pattern in good_patterns)
            if is_datasheet:
                result["quality_tier"] = "tier_2_datasheet_page"
                filtered.append(result)
                continue
            
            # PRIORITY 6: Accept manufacturer domains and repositories
            if domain in self.open_repositories or self._is_manufacturer_domain(domain):
                result["quality_tier"] = "tier_3_official"
                filtered.append(result)
                continue
            
            # PRIORITY 7: Accept everything else (might be distributor spec pages)
            result["quality_tier"] = "tier_4_other"
            filtered.append(result)
        
        logger.info(
            "Source quality filter: %d → %d results (rejected %d low-quality sources)",
            len(results),
            len(filtered),
            len(results) - len(filtered)
        )
        
        return filtered

    # --------------------------------------------------------------------------
    # _extract_domain()
    # --------------------------------------------------------------------------
    # Extracts clean domain from URL.
    # "https://www.solaredge.com/datasheet.pdf" → "solaredge.com"
    # --------------------------------------------------------------------------
    def _extract_domain(self, url: str) -> str:

        try:
            parsed = urlparse(url)
            domain = parsed.netloc

            if domain.startswith("www."):
                domain = domain[4:]

            return domain.lower()

        except Exception:
            return ""

    def _is_pdf_url(self, url: str) -> bool:
        try:
            return urlparse(url).path.lower().endswith(".pdf")
        except Exception:
            return url.lower().endswith(".pdf")

    def _is_manufacturer_domain(self, domain: str) -> bool:
        """Return True when domain matches any known manufacturer root or subdomain."""
        if not domain:
            return False

        clean = domain.lower().strip()
        if clean.startswith("www."):
            clean = clean[4:]

        manufacturer_roots = {
            "solaredge.com",
            "enphase.com",
            "fronius.com",
            "sma-america.com",
            "tesla.com",
            "generac.com",
            "panasonic.com",
            "qcells.com",
            "canadiansolar.com",
            "trinasolar.com",
            "jinkosolar.com",
            "longi.com",
            "sunpower.com",
            "apsystems.com",
            "tigoenergy.com",
            "hoymiles.com",
            "schneider-electric.com",
            "recgroup.com",
            "siemens.com",
            "eaton.com",
        }

        for root in manufacturer_roots:
            if clean == root or clean.endswith(f".{root}"):
                return True
        return False

    # --------------------------------------------------------------------------
    # _get_manufacturer_domain()
    # --------------------------------------------------------------------------
    # Returns the official domain for a manufacturer name.
    # Used to build targeted site: search queries.
    # --------------------------------------------------------------------------
    def _get_manufacturer_domain(self, manufacturer: str) -> str:

        MANUFACTURER_DOMAINS = {
            "solaredge":        "solaredge.com",
            "enphase":          "enphase.com",
            "fronius":          "fronius.com",
            "sma":              "sma-america.com",
            "tesla":            "tesla.com",
            "generac":          "generac.com",
            "panasonic":        "panasonic.com",
            "qcells":           "qcells.com",
            "canadian solar":   "canadiansolar.com",
            "trina":            "trinasolar.com",
            "trinasolar":       "trinasolar.com",
            "jinko":            "jinkosolar.com",
            "jinkosolar":       "jinkosolar.com",
            "longi":            "longi.com",
            "sunpower":         "sunpower.com",
            "apsystems":        "apsystems.com",
            "tigo":             "tigoenergy.com",
            "hoymiles":         "hoymiles.com",
            "schneider":        "schneider-electric.com",
            "rec":              "recgroup.com",
            "siemens":          "siemens.com",
            "eaton":            "eaton.com",
            "ironridge":        "ironridge.com",
        }

        key = manufacturer.strip().lower()

        # Exact match
        if key in MANUFACTURER_DOMAINS:
            return MANUFACTURER_DOMAINS[key]

        # Partial match
        for known_name, domain in MANUFACTURER_DOMAINS.items():
            if known_name in key or key in known_name:
                return domain

        return ""

    def _build_ironridge_candidate_urls(self, model: str) -> List[str]:
        """Build likely official IronRidge cut-sheet URLs for rail products."""
        normalized = (model or "").upper()
        compact = re.sub(r"[^A-Z0-9]", "", normalized)

        # Extract XR rail token when available (e.g., XR10, XR100, XR1000)
        token_match = re.search(r"XR\d{1,4}", compact)
        candidates = []
        if token_match:
            token = token_match.group(0)
            candidates.append(
                f"https://files.ironridge.com/roofmounting/cutsheets/IronRidge_Cut_Sheet_{token}_Rail.pdf"
            )

        # User-reported known official patterns (keep as fallback probes)
        for token in ["XR10", "XR100", "XR1000"]:
            candidates.append(
                f"https://files.ironridge.com/roofmounting/cutsheets/IronRidge_Cut_Sheet_{token}_Rail.pdf"
            )

        # Preserve order while deduplicating
        ordered_unique = []
        seen = set()
        for url in candidates:
            if url not in seen:
                ordered_unique.append(url)
                seen.add(url)
        return ordered_unique

    def _probe_pdf_url(self, url: str) -> bool:
        """Check if a PDF URL is reachable with a light HEAD/GET probe."""
        try:
            head_resp = requests.head(url, timeout=6, allow_redirects=True)
            if head_resp.status_code == 200:
                content_type = (head_resp.headers.get("Content-Type") or "").lower()
                return "pdf" in content_type or url.lower().endswith(".pdf")
        except Exception:
            pass

        try:
            get_resp = requests.get(url, timeout=8, stream=True)
            return get_resp.status_code == 200
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # get_api_credits()
    # --------------------------------------------------------------------------
    # Fetches the current API credit balance from Serper.
    # Returns: dict with credit info or error message
    # --------------------------------------------------------------------------
    def get_api_credits(self) -> dict:
        """
        Fetch API credit balance from Serper account endpoint.
        
        Returns:
            {
                "success": bool,
                "credits_remaining": int,
                "credits_used": int,
                "credits_total": int,
                "status": "ok" | "warning" | "critical" | "error",
                "message": str
            }
        """
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(
                settings.SERPER_QUOTA_ENDPOINT,
                headers=headers,
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            # Serper API returns: {"balance": 2500, "rateLimit": 5}
            credits_remaining = data.get("balance", 0)
            credits_used = 0  # Serper doesn't provide this in account endpoint
            credits_total = credits_remaining  # Total = current balance (simplified)

            # Determine status based on thresholds
            if credits_remaining <= settings.SERPER_CREDIT_CRITICAL_THRESHOLD:
                status = "critical"
                severity = "🔴 CRITICAL"
            elif credits_remaining <= settings.SERPER_CREDIT_WARNING_THRESHOLD:
                status = "warning"
                severity = "🟡 WARNING"
            else:
                status = "ok"
                severity = "✅ OK"

            message = f"{severity}: {credits_remaining} Serper credits remaining"

            # Log the status
            if status == "critical":
                logger.error(message)
            elif status == "warning":
                logger.warning(message)
            else:
                logger.info(message)

            return {
                "success": True,
                "credits_remaining": credits_remaining,
                "credits_used": credits_used,
                "credits_total": credits_total,
                "status": status,
                "message": message
            }

        except requests.Timeout:
            logger.error("Serper API timeout when fetching credits")
            return {
                "success": False,
                "credits_remaining": 0,
                "credits_used": 0,
                "credits_total": 0,
                "status": "error",
                "message": "❌ Timeout: Could not fetch Serper API credits"
            }

        except requests.HTTPError as e:
            logger.error("Serper API HTTP error when fetching credits: %s", str(e))
            return {
                "success": False,
                "credits_remaining": 0,
                "credits_used": 0,
                "credits_total": 0,
                "status": "error",
                "message": f"❌ API Error: {str(e)}"
            }

        except Exception as e:
            logger.error("Serper API error when fetching credits: %s", str(e))
            return {
                "success": False,
                "credits_remaining": 0,
                "credits_used": 0,
                "credits_total": 0,
                "status": "error",
                "message": f"❌ Error: {str(e)}"
            }

    # --------------------------------------------------------------------------
    # check_credits_before_search()
    # --------------------------------------------------------------------------
    # Checks if enough credits are available before making a search.
    # Returns: bool (True if search should proceed, False if credits exhausted)
    # --------------------------------------------------------------------------
    def check_credits_before_search(self) -> bool:
        """
        Check if API has credits before attempting search.
        If credits are critical/exhausted, returns False and logs error.
        """
        credit_info = self.get_api_credits()

        if not credit_info["success"]:
            logger.warning("Could not fetch credit info, continuing anyway")
            return True  # Continue anyway if we can't check

        credits_remaining = credit_info["credits_remaining"]

        if credits_remaining <= 0:
            logger.error(
                "🔴 SERPER CREDITS EXHAUSTED! No credits remaining. "
                "Please add more credits to your Serper account: "
                "https://serper.dev/account"
            )
            return False

        if credit_info["status"] == "critical":
            logger.warning(
                "🟡 Serper credits critical: Only %d credits remaining. "
                "Consider adding more credits soon!",
                credits_remaining
            )

        return True  # Allow search to proceed