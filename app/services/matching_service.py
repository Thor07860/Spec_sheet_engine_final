# ==============================================================================
# services/matching_service.py
# ------------------------------------------------------------------------------
# PURPOSE:
#   Handles fuzzy model name matching between what PMS sends us
#   and what actually appears in search results or spec sheets.
#
# THE PROBLEM IT SOLVES:
#   PMS sends:        "SE7600"
#   Spec sheet says:  "SE7600H-US"
#
#   These are the same product but the strings don't match exactly.
#   Without fuzzy matching, we'd miss the spec sheet entirely.
#
# HOW IT WORKS:
#   Uses RapidFuzz library to calculate string similarity percentage.
#   If similarity >= MIN_MATCH_SCORE (80% default), we accept the match.
#   We record the match type (exact / approximate / not_found) in the log.
#
# RULE:
#   This file ONLY handles model name matching logic.
#   It does NOT search, extract, or validate.
# ==============================================================================

from rapidfuzz import fuzz, process  # fuzzy string matching library
from typing import List, Optional
import logging
import re

from app.core.config import settings
from app.models.equipment_model import MatchType

logger = logging.getLogger(__name__)


class MatchingService:

    def __init__(self):
        # Minimum similarity score to accept a match (from .env, default 80.0)
        # Below this threshold → NOT_FOUND
        self.min_score = settings.MIN_MATCH_SCORE

    # --------------------------------------------------------------------------
    # find_best_match()
    # --------------------------------------------------------------------------
    # Given the input model name and a list of candidate model names found
    # during search, find the best matching candidate.
    #
    # Parameters:
    #   input_model  — what PMS sent us e.g. "SE7600"
    #   candidates   — list of model strings found in search results
    #                  e.g. ["SE7600H-US", "SE5000H-US", "SE7600H"]
    #
    # Returns a dict:
    #   {
    #     "matched_model": "SE7600H-US",
    #     "similarity_score": 94.5,
    #     "match_type": MatchType.APPROXIMATE
    #   }
    # --------------------------------------------------------------------------
    def find_best_match(
        self,
        input_model: str,
        candidates: List[str]
    ) -> dict:

        if not candidates:
            # No candidates to match against
            logger.warning("No candidates provided for matching: %s", input_model)
            return self._no_match_result(input_model)

        candidates = [candidate for candidate in candidates if self._is_valid_candidate(candidate)]

        if not candidates:
            logger.warning("No valid candidates remained after filtering for matching: %s", input_model)
            return self._no_match_result(input_model)

        # Normalize input for comparison
        # WHY: "SE7600H-US" and "se7600h-us" should match
        normalized_input = self._normalize(input_model)

        # Check for exact match first — fastest path
        for candidate in candidates:
            if self._normalize(candidate) == normalized_input:
                logger.info(
                    "Exact match: input=%s matched=%s", input_model, candidate
                )
                return {
                    "matched_model": candidate,
                    "similarity_score": 100.0,
                    "match_type": MatchType.EXACT
                }

        # No exact match — try fuzzy matching
        # process.extractOne() finds the single best match from the candidates list
        # scorer=fuzz.WRatio uses a weighted combination of multiple algorithms
        # WHY WRatio: More accurate than simple ratio for model names with
        #             hyphens, numbers, and suffixes like "-US" or "H"
        best = process.extractOne(
            normalized_input,
            [self._normalize(c) for c in candidates],
            scorer=fuzz.WRatio
        )

        if best is None:
            return self._no_match_result(input_model)

        # best = (matched_string, score, index)
        matched_normalized, score, index = best
        matched_original = candidates[index]    # get original (un-normalized) candidate

        logger.info(
            "Fuzzy match: input=%s matched=%s score=%.1f",
            input_model, matched_original, score
        )

        if score >= self.min_score:
            # Score is above threshold — accept as approximate match
            return {
                "matched_model": matched_original,
                "similarity_score": round(score, 2),
                "match_type": MatchType.APPROXIMATE
            }
        else:
            # Score too low — not a reliable match
            logger.warning(
                "Match score %.1f below threshold %.1f for input=%s",
                score, self.min_score, input_model
            )
            return self._no_match_result(input_model)

    # --------------------------------------------------------------------------
    # extract_model_candidates_from_text()
    # --------------------------------------------------------------------------
    # Extract all potential model name candidates from document text.
    # Generates n-grams (1-word, 2-word, 3-word combinations) as candidates.
    #
    # WHY THIS IS NEEDED:
    #   A spec sheet might contain text like:
    #   "SolarEdge SE7600H-US Single Phase Inverter Datasheet"
    #   We extract all tokens and n-gram combinations as candidates:
    #   ["SolarEdge", "SE7600H-US", "Single", "Phase", "Inverter", "Datasheet",
    #    "SolarEdge SE7600H-US", "SE7600H-US Single", "Single Phase", ...]
    #
    # These candidates are then scored against the requested model name
    # via find_best_match() to find the most likely match.
    # --------------------------------------------------------------------------
    def extract_model_candidates_from_text(self, text: str) -> List[str]:
        """Extract candidate model name tokens from document text."""
        
        if not text or not text.strip():
            return []

        # Split text into word tokens, limit to first section to avoid noise
        # (model names appear early in spec sheets)
        tokens = text.split()[:100]  # First 100 words should be enough
        
        if not tokens:
            return []

        # Generate n-grams: single words, pairs, triplets
        # Example text "SE7600H-US Single Phase" →
        #   ["SE7600H-US", "Single", "Phase",
        #    "SE7600H-US Single", "Single Phase",
        #    "SE7600H-US Single Phase"]
        candidates = []
        for n in range(1, 4):  # 1-gram, 2-gram, 3-gram
            for i in range(len(tokens) - n + 1):
                ngram = " ".join(tokens[i:i + n])
                if ngram not in candidates:  # avoid duplicates
                    candidates.append(ngram)
        
        logger.debug(
            "Extracted %d candidate tokens from document (total %d tokens)",
            len(candidates), len(tokens)
        )
        return candidates

    # --------------------------------------------------------------------------
    # extract_model_from_text()
    # --------------------------------------------------------------------------
    # Given raw text from a spec sheet or webpage title, extract the model
    # name that most closely matches the input model.
    #
    # WHY THIS IS NEEDED:
    #   A spec sheet title might say:
    #   "SolarEdge SE7600H-US Single Phase Inverter Datasheet"
    #   We need to extract "SE7600H-US" from that sentence.
    #
    # Strategy:
    #   Extract all candidates and find the best match.
    # --------------------------------------------------------------------------
    def extract_model_from_text(
        self,
        input_model: str,
        text: str
    ) -> Optional[str]:

        if not text:
            return None

        # Extract all candidate tokens from the text
        candidates = self.extract_model_candidates_from_text(text)

        if not candidates:
            return None

        result = self.find_best_match(input_model, candidates)

        if result["match_type"] == MatchType.NOT_FOUND:
            return None

        return result["matched_model"]

    # --------------------------------------------------------------------------
    # _normalize()
    # --------------------------------------------------------------------------
    # Normalize a model name string for consistent comparison.
    #
    # Transformations:
    #   "SE7600H-US" → "se7600h us"
    #   "IQ8M-72-2-US" → "iq8m 72 2 us"
    #
    # WHY REMOVE HYPHENS:
    #   "SE7600H-US" and "SE7600H US" should match.
    #   Manufacturers inconsistently use hyphens vs spaces.
    # --------------------------------------------------------------------------
    def _normalize(self, model: str) -> str:

        return (
            model
            .strip()
            .lower()
            .replace("-", " ")      # hyphens → spaces
            .replace("_", " ")      # underscores → spaces
            .replace(".", " ")      # dots → spaces (some models use "5.0")
        )

    def _is_valid_candidate(self, candidate: str) -> bool:
        normalized = self._normalize(candidate)

        if len(normalized.strip()) < 3:
            return False

        if not re.search(r"[a-zA-Z]", normalized):
            return False

        return True

    # --------------------------------------------------------------------------
    # _no_match_result()
    # --------------------------------------------------------------------------
    # Returns a standard NOT_FOUND result dict.
    # Centralized so the format is always consistent.
    # --------------------------------------------------------------------------
    def _no_match_result(self, input_model: str) -> dict:

        return {
            "matched_model": None,
            "similarity_score": 0.0,
            "match_type": MatchType.NOT_FOUND
        }