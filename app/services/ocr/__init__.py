"""
Modular OCR Subsystem
Khmer Government Document Intelligence System
"""

from typing import Optional
from app.config import settings
from app.services.ocr.base import BaseOCRProvider, OCRResultDTO
from app.services.ocr.tesseract_provider import TesseractProvider
from app.services.ocr.ollama_provider import OllamaProvider
from app.services.ocr.hybrid_provider import HybridProvider
from app.services.ocr.postprocessing import normalize_khmer_unicode, calculate_khmer_character_ratio
from app.services.ocr.evaluation import calculate_cer, calculate_wer, evaluate_ocr_result

# Global singleton provider registry
_providers = {
    "TESSERACT": TesseractProvider(),
    "OLLAMA": OllamaProvider(),
    "HYBRID": HybridProvider(),
}


def get_ocr_provider(name: Optional[str] = None) -> BaseOCRProvider:
    """
    Returns requested OCR provider or defaults to configured engine (TESSERACT or HYBRID).
    """
    target = (name or settings.DEFAULT_OCR_PROVIDER or "TESSERACT").upper()
    return _providers.get(target, _providers["TESSERACT"])


__all__ = [
    "BaseOCRProvider",
    "OCRResultDTO",
    "TesseractProvider",
    "OllamaProvider",
    "HybridProvider",
    "get_ocr_provider",
    "normalize_khmer_unicode",
    "calculate_khmer_character_ratio",
    "calculate_cer",
    "calculate_wer",
    "evaluate_ocr_result",
]
