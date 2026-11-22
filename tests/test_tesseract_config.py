"""
Test Tesseract Configuration and Availability
"""

import os
import pytest
from app.config import settings
from app.services.ocr_service import ocr_service


def test_tesseract_configuration_paths():
    """Verify centralized settings load correct Windows paths."""
    assert settings.TESSERACT_CMD is not None
    assert "tesseract.exe" in settings.TESSERACT_CMD.lower()
    clean_dir = settings.get_clean_tessdata_dir()
    assert '"' not in clean_dir
    assert "'" not in clean_dir


def test_tesseract_binary_exists():
    """Verify Tesseract OCR executable exists on the Windows system."""
    assert os.path.exists(settings.TESSERACT_CMD), (
        f"Tesseract executable not found at: {settings.TESSERACT_CMD}"
    )


def test_tesseract_environment_verification():
    """Verify Tesseract OCR status and languages check."""
    env = ocr_service.verify_environment()
    assert env["tesseract_installed"] is True
    assert env["tessdata_dir"] == settings.get_clean_tessdata_dir()
    # Ensure languages list is returned
    assert isinstance(env["languages_found"], list)
    assert len(env["languages_found"]) > 0


def test_english_language_available():
    """Verify 'eng.traineddata' is available to Tesseract."""
    langs = ocr_service.get_available_languages()
    assert "eng" in langs, f"English model 'eng' missing. Found: {langs}"


def test_khmer_language_available():
    """Verify 'khm.traineddata' is available to Tesseract."""
    langs = ocr_service.get_available_languages()
    assert "khm" in langs, f"Khmer model 'khm' missing. Found: {langs}"
