"""
Ollama Vision Language Model (VLM) OCR Provider
Khmer Government Document Intelligence System

Integrates local or remote vision models (e.g. Qwen2.5-VL, GLM-OCR, LLaVA, DeepSeek-OCR)
via Ollama REST API. Never automatically pulls models. Handles timeouts safely.
"""

import base64
import json
import logging
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from app.config import settings
from app.services.ocr.base import BaseOCRProvider, OCRResultDTO
from app.services.ocr.postprocessing import normalize_khmer_unicode

logger = logging.getLogger("ocr.ollama")


class OllamaProvider(BaseOCRProvider):
    """
    Ollama VLM OCR Provider for complex, handwritten, low-light, or structured documents.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model_name or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS

    @property
    def name(self) -> str:
        return "OLLAMA"

    def is_available(self) -> bool:
        """
        Pings Ollama service and checks if the configured model is installed locally.
        Zero auto-download: will return False if model is not already pulled.
        """
        if not settings.OLLAMA_ENABLED:
            return False

        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"User-Agent": "KhmerGovDocAI/1.0"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
                    target_base = self.model.split(":")[0]
                    return any(target_base in m for m in models)
            return False
        except Exception:
            return False

    def get_metadata(self) -> Dict[str, Any]:
        available = self.is_available()
        return {
            "provider": self.name,
            "base_url": self.base_url,
            "model_name": self.model,
            "timeout_seconds": self.timeout,
            "enabled_in_config": settings.OLLAMA_ENABLED,
            "ready": available,
        }

    def process(
        self,
        image_bytes: bytes,
        language: str = "khm+eng",
        options: Optional[Dict[str, Any]] = None,
    ) -> OCRResultDTO:
        start_time = time.time()
        opts = options or {}
        model = opts.get("model", self.model)

        b64_img = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "You are an expert OCR transcription engine for official Cambodian government documents "
            "and receipts. Transcribe every single visible line of text exactly as written, preserving "
            "both Khmer script (ភាសាខ្មែរ) and English numbers/characters. "
            "Do not summarize, do not translate, and do not add conversational preamble. "
            "Output only the transcribed raw text."
        )

        payload = {
            "model": model,
            "prompt": prompt,
            "images": [b64_img],
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic factual transcription
            }
        }

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Ollama server returned HTTP {resp.status}")
                res_data = json.loads(resp.read().decode("utf-8"))
                raw_text = res_data.get("response", "").strip()
        except urllib.error.URLError as err:
            logger.error(f"Ollama connection error: {err}")
            raise RuntimeError(f"Cannot reach Ollama service at {self.base_url}: {err}") from err
        except Exception as exc:
            logger.error(f"Ollama generation failure: {exc}")
            raise RuntimeError(f"Ollama OCR processing failed: {exc}") from exc

        elapsed_ms = int((time.time() - start_time) * 1000)
        cleaned_text = normalize_khmer_unicode(raw_text)

        # Estimate confidence based on non-empty extracted text
        confidence = 90.0 if len(cleaned_text) > 30 else 60.0

        return OCRResultDTO(
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            confidence=confidence,
            provider=self.name,
            model_name=model,
            execution_time_ms=elapsed_ms,
            languages=language,
            metadata={
                "base_url": self.base_url,
                "eval_duration_ms": elapsed_ms,
            }
        )
