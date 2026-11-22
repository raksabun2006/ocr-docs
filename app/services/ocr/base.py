"""
Base OCR Provider Interface
Khmer Government Document Intelligence System
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class OCRResultDTO:
    """Standardized Data Transfer Object for OCR Extraction Results."""
    raw_text: str
    cleaned_text: str
    confidence: float
    provider: str
    model_name: str
    execution_time_ms: int
    languages: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "cleaned_text": self.cleaned_text,
            "confidence": round(self.confidence, 2),
            "provider": self.provider,
            "model_name": self.model_name,
            "execution_time_ms": self.execution_time_ms,
            "languages": self.languages,
            "metadata": self.metadata,
        }


class BaseOCRProvider(ABC):
    """Abstract interface for all OCR recognition engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier: TESSERACT, OLLAMA, HYBRID."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if provider binary/service and required models are reachable."""
        pass

    @abstractmethod
    def process(
        self,
        image_bytes: bytes,
        language: str = "khm+eng",
        options: Optional[Dict[str, Any]] = None,
    ) -> OCRResultDTO:
        """Executes text recognition and returns standardized OCRResultDTO."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Returns provider status, version, and model capabilities."""
        pass
