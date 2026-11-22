"""
Tesseract OCR Service
Khmer Government Document Intelligence System

Integrates Tesseract OCR for English + Khmer language processing:
- Robust multi-language extraction (`khm+eng`).
- Clean tessdata directory and environment variable handling on Windows 11.
- Word-level confidence scoring and bounding box extraction for human verification.
- Safe error handling without revealing internal server paths or stack traces.
"""

import os
import logging
from typing import Dict, List, Any, Optional
import numpy as np
import pytesseract
from pytesseract import Output, TesseractError, TesseractNotFoundError

from app.config import settings

logger = logging.getLogger("ocr_service")


class OCRError(Exception):
    """Raised when an error occurs during OCR processing."""
    pass


class OCRConfigurationError(OCRError):
    """Raised when Tesseract or requested language packs are missing."""
    pass


class OCRService:
    """Manages Tesseract OCR execution, language verification, and structured data extraction."""

    def __init__(self):
        self.tesseract_cmd = settings.TESSERACT_CMD
        self.tessdata_dir = settings.get_clean_tessdata_dir()
        self.default_languages = settings.OCR_DEFAULT_LANGUAGES
        self._env_cache = None
        self._initialize_pytesseract()

    def _initialize_pytesseract(self) -> None:
        """Configures pytesseract command and environment variables."""
        if os.path.exists(self.tesseract_cmd):
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        if self.tessdata_dir and os.path.isdir(self.tessdata_dir):
            os.environ["TESSDATA_PREFIX"] = self.tessdata_dir

    def get_tessdata_config_arg(self) -> str:
        """
        Builds the clean command-line argument for --tessdata-dir without quotes
        that can break on Windows Tesseract CLI.
        """
        if self.tessdata_dir and os.path.isdir(self.tessdata_dir):
            clean_dir = self.tessdata_dir.replace("\\", "/")
            return f"--tessdata-dir {clean_dir}"
        return ""

    def is_tesseract_installed(self) -> bool:
        """Checks if the configured Tesseract executable exists and responds."""
        if not os.path.exists(self.tesseract_cmd):
            return False
        try:
            _ = pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def get_available_languages(self) -> List[str]:
        """Lists all trained data language models available to Tesseract."""
        try:
            config_arg = self.get_tessdata_config_arg()
            langs = pytesseract.get_languages(config=config_arg)
            return langs
        except Exception as exc:
            logger.warning(f"Could not retrieve available languages from Tesseract: {exc}")
            # Check filesystem directly as fallback
            found = []
            if self.tessdata_dir and os.path.isdir(self.tessdata_dir):
                for fname in os.listdir(self.tessdata_dir):
                    if fname.endswith(".traineddata"):
                        found.append(fname.replace(".traineddata", ""))
            return found

    def verify_environment(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Verifies Tesseract installation and presence of required English and Khmer models.
        Caches the result to avoid spawning heavy CLI subprocesses on repeated health calls.
        """
        if self._env_cache is not None and not force_refresh:
            return self._env_cache

        installed = self.is_tesseract_installed()
        langs = self.get_available_languages()
        has_eng = "eng" in langs
        has_khm = "khm" in langs

        self._env_cache = {
            "tesseract_installed": installed,
            "tesseract_cmd": self.tesseract_cmd,
            "tessdata_dir": self.tessdata_dir,
            "languages_found": langs,
            "has_english": has_eng,
            "has_khmer": has_khm,
            "ready_for_ocr": installed and has_eng and has_khm,
        }
        return self._env_cache

    def extract_text(
        self,
        image: np.ndarray,
        languages: Optional[str] = None,
        psm: int = 3
    ) -> str:
        """
        Extracts plain text from a preprocessed image using Tesseract.

        Args:
            image: Preprocessed OpenCV image array.
            languages: Plus-separated language code (default: 'khm+eng').
            psm: Page segmentation mode (default 3: Fully automatic).
        """
        lang = languages or self.default_languages
        config_parts = []
        tess_arg = self.get_tessdata_config_arg()
        if tess_arg:
            config_parts.append(tess_arg)
        config_parts.append(f"--psm {psm}")
        custom_config = " ".join(config_parts)

        try:
            text = pytesseract.image_to_string(
                image,
                lang=lang,
                config=custom_config
            )
            return text.strip()
        except TesseractNotFoundError:
            raise OCRConfigurationError("Tesseract OCR executable not found on the server.")
        except TesseractError as te:
            logger.error(f"Tesseract engine execution failed: {te}")
            raise OCRError("Document OCR extraction encountered an internal processing error.")
        except Exception as exc:
            logger.error(f"Unexpected error during OCR: {exc}")
            raise OCRError("Unable to complete document text extraction.")

    def extract_structured_ocr_data(
        self,
        image: np.ndarray,
        languages: Optional[str] = None,
        psm: int = 3
    ) -> Dict[str, Any]:
        """
        Extracts detailed word-level OCR output including confidence scores and bounding boxes.
        Used to highlight uncertain OCR results in human verification workflows.
        """
        lang = languages or self.default_languages
        config_parts = []
        tess_arg = self.get_tessdata_config_arg()
        if tess_arg:
            config_parts.append(tess_arg)
        config_parts.append(f"--psm {psm}")
        custom_config = " ".join(config_parts)

        try:
            data = pytesseract.image_to_data(
                image,
                lang=lang,
                config=custom_config,
                output_type=Output.DICT
            )

            words = []
            total_conf = 0.0
            valid_word_count = 0

            n_boxes = len(data["text"])
            for i in range(n_boxes):
                text = data["text"][i].strip()
                conf = float(data["conf"][i])

                # Tesseract returns -1 for spaces and layout delimiters
                if conf < 0 or not text:
                    continue

                valid_word_count += 1
                total_conf += conf

                # Flag uncertainty level based on configuration thresholds
                uncertainty = "low_uncertainty"
                if conf < settings.CONFIDENCE_THRESHOLD_MEDIUM:
                    uncertainty = "high_uncertainty"
                elif conf < settings.CONFIDENCE_THRESHOLD_HIGH:
                    uncertainty = "medium_uncertainty"

                words.append({
                    "text": text,
                    "confidence": round(conf, 2),
                    "uncertainty_level": uncertainty,
                    "box": {
                        "left": data["left"][i],
                        "top": data["top"][i],
                        "width": data["width"][i],
                        "height": data["height"][i]
                    }
                })

            average_confidence = round(total_conf / valid_word_count, 2) if valid_word_count > 0 else 0.0

            return {
                "average_confidence": average_confidence,
                "total_words": valid_word_count,
                "words": words,
            }
        except Exception as exc:
            logger.error(f"Structured OCR extraction error: {exc}")
            raise OCRError("Failed to extract structured OCR coordinates and confidence metrics.")


ocr_service = OCRService()
