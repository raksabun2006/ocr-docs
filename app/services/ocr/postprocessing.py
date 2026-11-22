"""
Khmer Unicode Post-Processing & Text Normalization Module
Khmer Government Document Intelligence System

Normalizes extracted Khmer script into canonical Unicode NFC form, eliminates zero-width
noise artifacts, fixes erroneous duplicate coengs/subscripts, and preserves formatting.
"""

import re
import unicodedata
from typing import Tuple


def normalize_khmer_unicode(text: str) -> str:
    """
    Applies standard Unicode NFC normalization and Khmer-specific typographical corrections.
    """
    if not text:
        return ""

    # 1. Unicode NFC Normalization (canonical decomposition followed by canonical composition)
    normalized = unicodedata.normalize("NFC", text)

    # 2. Fix multiple consecutive Khmer Coeng (Subscript signs: U+17D2)
    # A base consonant can only be followed by a single Coeng before the subscript consonant.
    normalized = re.sub(r"\u17D2{2,}", "\u17D2", normalized)

    # 3. Clean zero-width space clutter while preserving semantic separation
    # Replace multiple zero-width spaces or joins with single space or empty
    normalized = re.sub(r"[\u200B\u200C\u200D]{2,}", "\u200B", normalized)

    # 4. Standardize Cambodian punctuation
    # Normalize Khan (U+17D4 ៕) and Baryosan (U+17D5 ៖)
    normalized = re.sub(r"\s+([\u17D4\u17D5])", r"\1", normalized)

    # 5. Clean excessive repetitive blank lines
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    # 6. Strip trailing/leading edge spaces per line
    lines = [line.strip() for line in normalized.splitlines()]
    return "\n".join(lines).strip()


def calculate_khmer_character_ratio(text: str) -> Tuple[float, int, int]:
    """
    Calculates the proportion of Khmer script characters (U+1780 to U+17FF)
    versus total alphanumeric characters.
    Returns: (ratio, khmer_count, total_count)
    """
    if not text:
        return 0.0, 0, 0

    khmer_chars = 0
    total_chars = 0

    for ch in text:
        if ch.isspace():
            continue
        total_chars += 1
        cp = ord(ch)
        if 0x1780 <= cp <= 0x17FF or 0x19E0 <= cp <= 0x19FF:
            khmer_chars += 1

    ratio = (khmer_chars / total_chars) if total_chars > 0 else 0.0
    return ratio, khmer_chars, total_chars
