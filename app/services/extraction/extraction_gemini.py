# ==============================================================================
# services/extraction/extraction_gemini.py
# ==============================================================================
# PURPOSE
#   Wrapper for Gemini API calls (vision, grounded searches, schema building)
# ==============================================================================

import json
import logging
import os
from typing import Optional, Any, Tuple
import google.generativeai as genai
from app.core.config import settings
from .extraction_parsing import ExtractionParser

logger = logging.getLogger(__name__)


class GeminiCaller:
    """Wrapper for Gemini AI API calls (vision, grounded search, etc.)"""

    def __init__(self):
        self.parser = ExtractionParser()
        # Configure SDK once so all model calls (including detection) are authenticated.
        api_key = settings.GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        else:
            logger.error(
                "Gemini API key is missing. Set GEMINI_API_KEY in .env or GOOGLE_API_KEY in environment."
            )

    def call_gemini(
        self,
        prompt: str,
        pdf_data: Optional[bytes] = None,
        model: str = "gemini-2.0-flash",
        temperature: int = 0,
        max_tokens: int = 4096
    ) -> Tuple[Optional[dict], dict]:
        """
        Call Gemini with optional PDF vision.
        
        Args:
            prompt: Text prompt for Gemini
            pdf_data: PDF file bytes for vision processing
            model: Gemini model to use
            temperature: 0 = strict mode, higher = creative
            max_tokens: Maximum response tokens
        
        Returns:
            Tuple of (parsed_response, token_usage)
            token_usage = {"input_tokens": N, "output_tokens": N, "total_tokens": N}
        """
        default_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        
        try:
            gemini_model = genai.GenerativeModel(model)
            contents = [prompt]

            # Add PDF as vision content if provided
            if pdf_data:
                pdf_part = {
                    "mime_type": "application/pdf",
                    "data": pdf_data
                }
                contents = [prompt, pdf_part]

            response = gemini_model.generate_content(
                contents,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
            )

            # Extract token usage
            tokens = default_tokens.copy()
            if response and hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                tokens = {
                    "input_tokens": getattr(usage, "prompt_token_count", 0),
                    "output_tokens": getattr(usage, "candidates_token_count", 0),
                    "total_tokens": getattr(usage, "total_token_count", 0)
                }
            
            if response and response.text:
                # Central parser handles plain JSON, markdown JSON blocks, and embedded JSON.
                parsed = self.parser.parse_response(response.text)
                return parsed, tokens

            logger.warning("Empty Gemini response")
            return None, tokens

        except Exception as e:
            logger.error(f"Gemini call failed: {e}")
            return None, default_tokens

    def call_gemini_grounded(
        self,
        prompt: str,
        model: str = "gemini-3.1-pro-preview",
        temperature: int = 0
    ) -> Tuple[Optional[dict], dict]:
        """
        Call Gemini with Google Search tool for grounded fallback.
        Gemini can search real-time web for missing specs.
        
        Args:
            prompt: Detailed prompt with equipment details + missing fields
            model: Gemini model with search access
            temperature: 0 = strict mode
        
        Returns:
            Tuple of (parsed_response, token_usage)
        """
        default_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        
        try:
            # Enable Google Search tool
            tools = [genai.Tool(google_search_retrieval=genai.types.GoogleSearchRetrieval())]
            gemini_model = genai.GenerativeModel(model, tools=tools)

            response = gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=4096
                ),
                tool_config=genai.types.ToolConfig(
                    function_calling_config="ANY"  # Always use the tool
                )
            )

            # Extract token usage
            tokens = default_tokens.copy()
            if response and hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                tokens = {
                    "input_tokens": getattr(usage, "prompt_token_count", 0),
                    "output_tokens": getattr(usage, "candidates_token_count", 0),
                    "total_tokens": getattr(usage, "total_token_count", 0)
                }
            
            if response and response.text:
                parsed = self.parser.parse_response(response.text)
                if parsed:
                    # Mark metadata so downstream confidence logic can treat
                    # grounded-web values differently from PDF-only values.
                    self.parser.apply_internet_confidence(parsed)
                    return parsed, tokens

            logger.warning("Empty grounded response from Gemini")
            return None, tokens

        except Exception as e:
            logger.error(f"Gemini grounded call failed: {e}")
            return None, default_tokens

    def detect_models_in_document(
        self,
        pdf_data: bytes,
        manufacturer: str
    ) -> Optional[list]:
        """
        Detect all model numbers in PDF using Gemini vision.
        Needed for cases where user uploaded wrong PDF.
        
        Args:
            pdf_data: PDF file bytes
            manufacturer: Equipment manufacturer name
        
        Returns:
            List of detected model numbers or None
        """
        try:
            prompt = f"""Scan this PDF document from {manufacturer} and extract EACH model number you can find.
            
            Return as JSON array:
            {{"models": ["model1", "model2", ...]}}"""

            gemini_model = genai.GenerativeModel("gemini-2.0-flash")
            response = gemini_model.generate_content(
                [prompt, {"mime_type": "application/pdf", "data": pdf_data}]
            )

            if response and response.text:
                parsed = self.parser.parse_response(response.text)
                if parsed and "models" in parsed:
                    return parsed["models"]

            return None

        except Exception as e:
            logger.error(f"Model detection failed: {e}")
            return None

    def build_response_json_schema(
        self,
        schema_template: dict
    ) -> dict:
        """
        Build JSON schema for Gemini's structured response.
        Forces Gemini to return JSON matching template fields.
        
        Args:
            schema_template: Equipment template dict with all fields
        
        Returns:
            JSON schema for response format
        """
        properties = {}
        for key in schema_template.keys():
            properties[key] = {"type": "string"}

        return {
            "type": "object",
            "properties": properties,
            "required": list(schema_template.keys())
        }
