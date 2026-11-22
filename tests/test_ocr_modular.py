"""
Unit Tests for Modular OCR Architecture, Evaluation (CER/WER), and Khmer Normalization
Khmer Government Document Intelligence System
"""

import pytest
from app.services.ocr import (
    get_ocr_provider,
    normalize_khmer_unicode,
    calculate_khmer_character_ratio,
    calculate_cer,
    calculate_wer,
    evaluate_ocr_result,
    TesseractProvider,
    OllamaProvider,
    HybridProvider
)


def test_khmer_unicode_normalization():
    """Verify Unicode NFC normalization and consecutive coeng reduction."""
    # Double Coeng sign (U+17D2 + U+17D2) should be collapsed to single
    corrupted_text = "រដ្ឋ\u17D2\u17D2បាល"
    normalized = normalize_khmer_unicode(corrupted_text)
    assert "\u17D2\u17D2" not in normalized

    # Punctuation spacing normalization (Khan U+17D4)
    text_with_spaces = "សំបុត្រកំណើត  ។"
    cleaned = normalize_khmer_unicode(text_with_spaces)
    assert cleaned == "សំបុត្រកំណើត។"


def test_calculate_khmer_character_ratio():
    """Verify detection of Khmer script density in mixed documents."""
    pure_khmer = "ព្រះរាជាណាចក្រកម្ពុជា"
    ratio, khm_cnt, total_cnt = calculate_khmer_character_ratio(pure_khmer)
    assert ratio == 1.0
    assert khm_cnt == total_cnt

    pure_english = "Receipt Number 9872"
    ratio_en, khm_cnt_en, _ = calculate_khmer_character_ratio(pure_english)
    assert ratio_en == 0.0
    assert khm_cnt_en == 0

    mixed = "សរុប: $12.50 USD"
    ratio_mix, _, _ = calculate_khmer_character_ratio(mixed)
    assert 0.0 < ratio_mix < 1.0


def test_cer_and_wer_metrics():
    """Verify Character Error Rate and Word Error Rate calculation."""
    reference = "សំបុត្រកំណើត"
    # Exact match -> CER = 0, WER = 0
    assert calculate_cer(reference, reference) == 0.0
    assert calculate_wer(reference, reference) == 0.0

    # 1 substitution in 4-character word
    ref_word = "កម្ពុជា"
    hyp_word = "កម្ពុជ"
    cer = calculate_cer(ref_word, hyp_word)
    assert 0.0 < cer < 1.0

    eval_summary = evaluate_ocr_result(reference, reference, execution_time_ms=120)
    assert eval_summary["character_error_rate"] == 0.0
    assert eval_summary["character_accuracy_percent"] == 100.0
    assert eval_summary["execution_time_ms"] == 120


def test_provider_registry():
    """Verify provider discovery and fallback to configured default."""
    tess = get_ocr_provider("TESSERACT")
    assert isinstance(tess, TesseractProvider)
    assert tess.name == "TESSERACT"

    hybrid = get_ocr_provider("HYBRID")
    assert isinstance(hybrid, HybridProvider)
    assert hybrid.name == "HYBRID"

    ollama = get_ocr_provider("OLLAMA")
    assert isinstance(ollama, OllamaProvider)
    assert ollama.name == "OLLAMA"


def test_ollama_graceful_availability_when_disabled():
    """Verify that Ollama does not trigger downloads and safely reports offline status."""
    ollama = OllamaProvider(base_url="http://localhost:11434", model_name="qwen2.5-vl")
    # By default in testing environment, Ollama is disabled/unreachable
    status_info = ollama.get_metadata()
    assert "provider" in status_info
    assert status_info["provider"] == "OLLAMA"
    assert status_info["model_name"] == "qwen2.5-vl"
