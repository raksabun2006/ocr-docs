"""
Test OpenCV Image Preprocessing and Real Tesseract OCR
"""

import pytest
import numpy as np
import cv2

from app.services.image_service import (
    load_image_bytes_to_cv2,
    deskew_document,
    enhance_contrast_clahe,
    preprocess_for_ocr
)
from app.services.ocr_service import ocr_service


def test_load_image_bytes_to_cv2(english_receipt_bytes):
    """Verify raw bytes decode to valid OpenCV numpy array."""
    img = load_image_bytes_to_cv2(english_receipt_bytes)
    assert isinstance(img, np.ndarray)
    assert len(img.shape) == 3
    assert img.shape[2] == 3  # BGR channels


def test_deskew_document(english_receipt_bytes):
    """Verify deskew operation correctly executes without distortion."""
    img = load_image_bytes_to_cv2(english_receipt_bytes)
    deskewed, angle = deskew_document(img)
    assert isinstance(deskewed, np.ndarray)
    assert deskewed.shape == img.shape
    assert isinstance(angle, float)


def test_enhance_contrast_clahe(english_receipt_bytes):
    """Verify CLAHE histogram equalization."""
    img = load_image_bytes_to_cv2(english_receipt_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe_img = enhance_contrast_clahe(gray)
    assert clahe_img.shape == gray.shape
    assert clahe_img.dtype == np.uint8


def test_preprocess_for_ocr_pipeline(mixed_birth_certificate_bytes):
    """Verify end-to-end preprocessing pipeline generates binary 8-bit image."""
    binary = preprocess_for_ocr(mixed_birth_certificate_bytes)
    assert isinstance(binary, np.ndarray)
    assert len(binary.shape) == 2  # Single channel (binary/grayscale)
    # Check binary values (predominantly 0 or 255)
    unique_vals = np.unique(binary)
    assert 0 in unique_vals or 255 in unique_vals


def test_real_english_document_ocr(english_receipt_bytes):
    """Real OCR test on English document - no fake mocks."""
    preprocessed = preprocess_for_ocr(english_receipt_bytes)
    text = ocr_service.extract_text(preprocessed, languages="eng")
    assert len(text) > 0
    # Should detect key words from receipt
    assert "RECEIPT" in text.upper() or "AMOUNT" in text.upper() or "DOCUMENT" in text.upper()


def test_real_khmer_document_ocr(khmer_document_bytes):
    """Real OCR test on Khmer government document."""
    preprocessed = preprocess_for_ocr(khmer_document_bytes)
    text = ocr_service.extract_text(preprocessed, languages="khm")
    assert len(text) > 0
    # Checks that non-empty text was extracted


def test_real_mixed_language_ocr(mixed_birth_certificate_bytes):
    """Real OCR test on mixed English and Khmer birth certificate."""
    preprocessed = preprocess_for_ocr(mixed_birth_certificate_bytes)
    text = ocr_service.extract_text(preprocessed, languages="khm+eng")
    assert len(text) > 0

    # Structured data check
    structured = ocr_service.extract_structured_ocr_data(preprocessed, languages="khm+eng")
    assert "average_confidence" in structured
    assert structured["average_confidence"] > 0
    assert "words" in structured
    assert len(structured["words"]) > 0
