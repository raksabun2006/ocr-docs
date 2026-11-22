"""
OCR Benchmarking & Accuracy Evaluation Module
Khmer Government Document Intelligence System

Calculates Character Error Rate (CER) and Word Error Rate (WER) using
Levenshtein distance algorithms between Ground Truth (Reference) and OCR output (Hypothesis).
"""

from typing import List, Dict, Any, Tuple
from app.services.ocr.postprocessing import normalize_khmer_unicode


def _levenshtein_distance(seq1: List[Any], seq2: List[Any]) -> int:
    """Computes Levenshtein distance between two sequences."""
    n, m = len(seq1), len(seq2)
    if n == 0:
        return m
    if m == 0:
        return n

    # Dynamic programming matrix with space optimization
    prev = list(range(m + 1))
    curr = [0] * (m + 1)

    for i in range(1, n + 1):
        curr[0] = i
        for j in range(1, m + 1):
            cost = 0 if seq1[i - 1] == seq2[j - 1] else 1
            curr[j] = min(
                curr[j - 1] + 1,      # Insertion
                prev[j] + 1,          # Deletion
                prev[j - 1] + cost    # Substitution
            )
        prev, curr = curr, [0] * (m + 1)

    return prev[m]


def calculate_cer(reference: str, hypothesis: str, normalize: bool = True) -> float:
    """
    Calculates Character Error Rate:
    CER = LevenshteinDistance(ref_chars, hyp_chars) / len(ref_chars)
    Returns a float (0.0 means 100% exact match).
    """
    if normalize:
        ref = normalize_khmer_unicode(reference)
        hyp = normalize_khmer_unicode(hypothesis)
    else:
        ref = reference
        hyp = hypothesis

    ref_chars = list(ref)
    hyp_chars = list(hyp)

    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0

    edit_dist = _levenshtein_distance(ref_chars, hyp_chars)
    return round(edit_dist / len(ref_chars), 4)


def calculate_wer(reference: str, hypothesis: str, normalize: bool = True) -> float:
    """
    Calculates Word Error Rate:
    WER = LevenshteinDistance(ref_words, hyp_words) / len(ref_words)
    Splits by whitespace or punctuation.
    """
    if normalize:
        ref = normalize_khmer_unicode(reference)
        hyp = normalize_khmer_unicode(hypothesis)
    else:
        ref = reference
        hyp = hypothesis

    ref_words = ref.split()
    hyp_words = hyp.split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    edit_dist = _levenshtein_distance(ref_words, hyp_words)
    return round(edit_dist / len(ref_words), 4)


def evaluate_ocr_result(
    reference: str,
    hypothesis: str,
    execution_time_ms: int = 0
) -> Dict[str, Any]:
    """
    Comprehensive evaluation summary comparing OCR output to ground truth.
    """
    norm_ref = normalize_khmer_unicode(reference)
    norm_hyp = normalize_khmer_unicode(hypothesis)

    cer = calculate_cer(norm_ref, norm_hyp, normalize=False)
    wer = calculate_wer(norm_ref, norm_hyp, normalize=False)

    accuracy_char = max(0.0, round((1.0 - cer) * 100, 2))
    accuracy_word = max(0.0, round((1.0 - wer) * 100, 2))

    return {
        "reference_len_chars": len(norm_ref),
        "hypothesis_len_chars": len(norm_hyp),
        "reference_len_words": len(norm_ref.split()),
        "hypothesis_len_words": len(norm_hyp.split()),
        "character_error_rate": cer,
        "word_error_rate": wer,
        "character_accuracy_percent": accuracy_char,
        "word_accuracy_percent": accuracy_word,
        "execution_time_ms": execution_time_ms,
    }
