"""
Hybrid OCR Provider Implementation
Khmer Government Document Intelligence System

Executes fast, deterministic Tesseract OCR first.
If document is handwritten, noisy, graph-ruled, or low confidence, and Ollama is online,
transparently cascades to Ollama Vision Model while preserving full auditability.
"""

import logging
from typing import Dict, Any, Optional

from app.services.ocr.base import BaseOCRProvider, OCRResultDTO
from app.services.ocr.tesseract_provider import TesseractProvider
from app.services.ocr.ollama_provider import OllamaProvider

logger = logging.getLogger("ocr.hybrid")


class HybridProvider(BaseOCRProvider):
    """
    Combines Tesseract OCR and Vision Language Model (Ollama) into an intelligent cascade.
    """

    def __init__(
        self,
        tesseract_provider: Optional[TesseractProvider] = None,
        ollama_provider: Optional[OllamaProvider] = None,
        confidence_threshold: float = 65.0,
    ):
        self.tesseract = tesseract_provider or TesseractProvider()
        self.ollama = ollama_provider or OllamaProvider()
        self.confidence_threshold = confidence_threshold

    @property
    def name(self) -> str:
        return "HYBRID"

    def is_available(self) -> bool:
        return self.tesseract.is_available() or self.ollama.is_available()

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "tesseract": self.tesseract.get_metadata(),
            "ollama": self.ollama.get_metadata(),
            "cascade_threshold": self.confidence_threshold,
        }

    def process(
        self,
        image_bytes: bytes,
        language: str = "khm+eng",
        options: Optional[Dict[str, Any]] = None,
    ) -> OCRResultDTO:
        opts = options or {}
        force_provider = opts.get("force_provider")

        # Handle explicit override
        if force_provider == "OLLAMA" and self.ollama.is_available():
            return self.ollama.process(image_bytes, language=language, options=opts)
        if force_provider == "TESSERACT":
            return self.tesseract.process(image_bytes, language=language, options=opts)

        # 1. Run local Tesseract first (low latency, 0 token cost)
        tess_res = self.tesseract.process(image_bytes, language=language, options=opts)

        # Check quality criteria
        text_len = len(tess_res.cleaned_text.strip())
        is_confident = tess_res.confidence >= self.confidence_threshold
        is_substantial = text_len >= 25

        if is_confident and is_substantial:
            tess_res.metadata["cascade_used"] = "TESSERACT_PRIMARY"
            return tess_res

        # 2. Check if Ollama is available for difficult/handwritten fallback
        if self.ollama.is_available():
            logger.info(
                f"Tesseract returned confidence={tess_res.confidence}%, chars={text_len}. "
                "Triggering Ollama VLM enhancement..."
            )
            try:
                ollama_res = self.ollama.process(image_bytes, language=language, options=opts)
                ollama_res.metadata["cascade_used"] = "OLLAMA_FALLBACK"
                ollama_res.metadata["tesseract_original_output"] = tess_res.raw_text
                ollama_res.metadata["tesseract_confidence"] = tess_res.confidence
                return ollama_res
            except Exception as exc:
                logger.warning(f"Ollama fallback failed: {exc}. Returning Tesseract result.")

        # Fallback to Tesseract if Ollama not available or failed
        tess_res.metadata["cascade_used"] = "TESSERACT_ONLY"
        return tess_res
