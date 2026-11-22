"""
Tesseract OCR Provider Implementation
Khmer Government Document Intelligence System
"""

import time
import logging
from typing import Dict, Any, Optional

from app.config import settings
from app.services.ocr.base import BaseOCRProvider, OCRResultDTO
from app.services.ocr.postprocessing import normalize_khmer_unicode
from app.services.ocr_service import ocr_service, OCRError

logger = logging.getLogger("ocr.tesseract")


class TesseractProvider(BaseOCRProvider):
    """
    Production Tesseract OCR Provider for Khmer + English documents.
    Supports multi-PSM fallback, shadow/graph paper suppression, and confidence scoring.
    """

    @property
    def name(self) -> str:
        return "TESSERACT"

    def is_available(self) -> bool:
        env = ocr_service.verify_environment()
        return bool(env.get("ready_for_ocr", False))

    def get_metadata(self) -> Dict[str, Any]:
        env = ocr_service.verify_environment()
        return {
            "provider": self.name,
            "binary_path": settings.TESSERACT_CMD,
            "tessdata_dir": env.get("tessdata_dir", ""),
            "available_languages": env.get("languages_found", []),
            "ready": env.get("ready_for_ocr", False),
            "khmer_available": env.get("has_khmer", False),
            "english_available": env.get("has_english", False),
        }

    def process(
        self,
        image_bytes: bytes,
        language: str = "khm+eng",
        options: Optional[Dict[str, Any]] = None,
    ) -> OCRResultDTO:
        start_time = time.time()
        opts = options or {}
        active_lang = language or settings.OCR_DEFAULT_LANGUAGES

        # Process via enhanced multi-PSM ocr_service
        raw_result = ocr_service.extract_text_from_bytes(image_bytes, language=active_lang)

        elapsed_ms = int((time.time() - start_time) * 1000)
        raw_text = raw_result.get("text", "")
        cleaned_text = normalize_khmer_unicode(raw_text)

        return OCRResultDTO(
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            confidence=raw_result.get("confidence", 0.0),
            provider=self.name,
            model_name="tesseract-5.x",
            execution_time_ms=elapsed_ms,
            languages=active_lang,
            metadata={
                "psm_used": raw_result.get("psm_used", "auto"),
                "total_words": raw_result.get("total_words", 0),
                "is_fallback": raw_result.get("is_fallback", False),
            }
        )
