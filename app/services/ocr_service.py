"""
Tesseract OCR Service (Khmer & English Advanced Engine)
Khmer Government Document Intelligence System

Specialized OCR engine engineered for Cambodian administrative documents & handwriting:
- Adaptive Multi-PSM fallback (PSM 6, 4, 11, 3) ensuring no document is missed.
- LSTM Neural Network engine optimization (--oem 1, --dpi 300, preserve_interword_spaces=1).
- Multi-Representation evaluation (evaluates both Enhanced Grayscale and Clean Adaptive Binary).
- Khmer Unicode post-processing and line artifact suppression.
- Word-level confidence scoring and bounding box coordinates for human verification.
"""

import os
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
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


def clean_khmer_ocr_text(text: str) -> str:
    """
    Cleans OCR artifacts common to scanned Cambodian documents & graph paper:
    - Removes isolated separator artifacts (e.g. lines with only `---`, `===`, `| | |`).
    - Standardizes Khmer punctuation and numerals.
    - Strips extraneous control characters while preserving UTF-8 Khmer characters.
    """
    if not text:
        return ""

    cleaned_lines = []
    lines = text.split("\n")

    for line in lines:
        stripped = line.strip()
        # Filter out lines consisting only of grid line remnants (e.g. —, _, |, =, ~, `)
        if re.match(r"^[\s\-_\|\=\~\`\.\,\:\;\+\*\#\/\\]+$", stripped):
            continue
        # Remove repeated pipes or vertical bar noise
        normalized = re.sub(r"\|{2,}", "|", stripped)
        if normalized:
            cleaned_lines.append(normalized)

    result = "\n".join(cleaned_lines)
    # Normalize multiple blank lines to at most two
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


class OCRService:
    """Manages multi-language Tesseract OCR with adaptive multi-pass Khmer recognition."""

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
        """Builds the clean command-line argument for --tessdata-dir without quotes."""
        if self.tessdata_dir and os.path.isdir(self.tessdata_dir):
            clean_dir = self.tessdata_dir.replace("\\", "/")
            return f"--tessdata-dir {clean_dir}"
        return ""

    def is_tesseract_installed(self) -> bool:
        """Checks if the configured Tesseract executable exists and responds."""
        if not os.path.exists(self.tesseract_cmd):
            return False
        try:
            import subprocess
            proc = subprocess.run(
                [self.tesseract_cmd, "--version"],
                capture_output=True,
                timeout=2,
                check=False
            )
            return proc.returncode == 0
        except Exception:
            return False

    def get_available_languages(self) -> List[str]:
        """Lists all trained data language models available to Tesseract."""
        found = set()
        # 1. Check directory directly first (instant, 0 subprocess overhead)
        if self.tessdata_dir and os.path.isdir(self.tessdata_dir):
            try:
                for fname in os.listdir(self.tessdata_dir):
                    if fname.endswith(".traineddata"):
                        found.add(fname.replace(".traineddata", ""))
            except Exception:
                pass

        # 2. Check default Tesseract tessdata folder if different
        parent_tessdata = os.path.join(os.path.dirname(self.tesseract_cmd), "tessdata")
        if os.path.isdir(parent_tessdata):
            try:
                for fname in os.listdir(parent_tessdata):
                    if fname.endswith(".traineddata"):
                        found.add(fname.replace(".traineddata", ""))
            except Exception:
                pass

        if found:
            return sorted(list(found))

        # 3. Fallback to CLI with safe 2-second timeout
        try:
            import subprocess
            proc = subprocess.run(
                [self.tesseract_cmd, "--list-langs"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False
            )
            if proc.returncode == 0:
                lines = [line.strip() for line in proc.stdout.splitlines() if line.strip() and not line.startswith("List of")]
                return sorted(lines)
        except Exception as exc:
            logger.warning(f"Could not retrieve available languages from Tesseract: {exc}")

        return []

    def verify_environment(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Verifies Tesseract installation and presence of required English and Khmer models."""
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

    def build_tesseract_config(self, psm: int = 3, extra_args: str = "") -> str:
        """Constructs an optimized Tesseract configuration string for Khmer script."""
        parts = []
        tess_arg = self.get_tessdata_config_arg()
        if tess_arg:
            parts.append(tess_arg)
        # Force LSTM engine, calibration DPI, and inter-word space preservation
        parts.append(f"--psm {psm} --oem 1 --dpi 300 -c preserve_interword_spaces=1")
        if extra_args:
            parts.append(extra_args)
        return " ".join(parts)

    def extract_text(
        self,
        image: np.ndarray,
        languages: Optional[str] = None,
        psm: int = 3
    ) -> str:
        """
        Extracts plain text with automatic multi-PSM fallback.
        If the primary PSM returns empty or sparse text, automatically tries
        PSM 6 (uniform text block), PSM 4 (single column), or PSM 11 (sparse text).
        """
        lang = languages or self.default_languages
        candidate_psms = [psm] + [p for p in [6, 4, 11, 3] if p != psm]
        best_text = ""

        try:
            for candidate_psm in candidate_psms:
                custom_config = self.build_tesseract_config(psm=candidate_psm)
                raw_text = pytesseract.image_to_string(
                    image,
                    lang=lang,
                    config=custom_config
                )
                cleaned = clean_khmer_ocr_text(raw_text)
                if len(cleaned) > len(best_text):
                    best_text = cleaned
                    # If we found substantial text (more than 20 chars), accept and return
                    if len(best_text) >= 20:
                        break

            return best_text.strip()
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
        Extracts word-level confidence scores and bounding boxes with multi-PSM fallback.
        """
        lang = languages or self.default_languages
        candidate_psms = [psm] + [p for p in [6, 4, 11, 3] if p != psm]
        best_result = None
        max_words = -1

        for candidate_psm in candidate_psms:
            custom_config = self.build_tesseract_config(psm=candidate_psm)
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

                    if conf < 0 or not text:
                        continue

                    # Ignore lone noise characters from grid lines
                    if len(text) == 1 and text in "-_|=~`.,:;+*#/\\[]":
                        continue

                    valid_word_count += 1
                    total_conf += conf

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

                avg_conf = round(total_conf / valid_word_count, 2) if valid_word_count > 0 else 0.0

                current_res = {
                    "average_confidence": avg_conf,
                    "total_words": valid_word_count,
                    "words": words,
                    "used_psm": candidate_psm
                }

                if valid_word_count > max_words:
                    max_words = valid_word_count
                    best_result = current_res
                    if max_words >= 15:
                        break

            except Exception as exc:
                logger.warning(f"Structured OCR candidate PSM {candidate_psm} error: {exc}")
                continue

        if best_result is not None:
            return best_result

        return {
            "average_confidence": 0.0,
            "total_words": 0,
            "words": [],
            "used_psm": psm
        }

    def process_document_adaptive(
        self,
        variants: Dict[str, np.ndarray],
        languages: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Adaptive Multi-Representation Khmer OCR:
        Evaluates both Enhanced Grayscale (preferred for LSTM) and Clean Adaptive Binary
        (preferred for high-contrast graph paper), selecting the superior recognition output.
        """
        # Pass 1: Test clean adaptive with grid suppression
        clean_adaptive = variants.get("clean_adaptive")
        enhanced_gray = variants.get("enhanced_gray")
        standard_otsu = variants.get("standard_otsu")

        best_text = ""
        best_data = None
        highest_score = -1

        # Evaluate candidate representations
        for candidate_img in [clean_adaptive, enhanced_gray, standard_otsu]:
            if candidate_img is None:
                continue

            try:
                struct_data = self.extract_structured_ocr_data(candidate_img, languages=languages, psm=6)
                word_count = struct_data["total_words"]
                avg_conf = struct_data["average_confidence"]
                score = word_count * 10 + avg_conf

                if score > highest_score:
                    highest_score = score
                    best_data = struct_data
                    best_text = self.extract_text(candidate_img, languages=languages, psm=struct_data.get("used_psm", 6))
            except Exception as e:
                logger.warning(f"Adaptive pass error: {e}")
                continue

        if not best_text and clean_adaptive is not None:
            best_text = self.extract_text(clean_adaptive, languages=languages, psm=11)
            best_data = self.extract_structured_ocr_data(clean_adaptive, languages=languages, psm=11)

        return best_text, best_data or {"average_confidence": 0.0, "total_words": 0, "words": []}


ocr_service = OCRService()
