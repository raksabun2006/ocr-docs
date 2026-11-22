"""
Test Structured Information Extraction for Khmer Birth Certificates
"""

import pytest
from app.services.extraction_service import (
    convert_khmer_numerals,
    birth_certificate_extractor
)


def test_convert_khmer_numerals():
    """Verify Khmer numeral conversion to Arabic numerals."""
    khmer_text = "ថ្ងៃទី ១៥ ខែ មេសា ឆ្នាំ ២០០០ លេខ 1234/២០២៤"
    converted = convert_khmer_numerals(khmer_text)
    assert "15" in converted
    assert "2000" in converted
    assert "2024" in converted


def test_extract_birth_certificate_full_fields():
    """Test extracting all fields from standard Cambodian birth certificate text."""
    sample_text = """
    ព្រះរាជាណាចក្រកម្ពុជា
    ជាតិ សាសនា ព្រះមហាក្សត្រ
    សេចក្តីចម្លងសំបុត្រកំណើត
    BIRTH CERTIFICATE
    
    គោត្តនាម និង នាម : សុខ សាន
    In Latin : SOK SAN
    ភេទ : ប្រុស
    កើតថ្ងៃទី : ១៥ ខែ មេសា ឆ្នាំ ២០០០
    ទីកន្លែងកំណើត : រាជធានីភ្នំពេញ
    ឪពុកឈ្មោះ : សុខ មករា
    ម្តាយឈ្មោះ : កែវ ធីតា
    លេខសំបុត្រ : 1234/2000
    ថ្ងៃចុះបញ្ជី : 20-04-2000
    """
    data = birth_certificate_extractor.extract(sample_text)

    assert data.full_name_khmer == "សុខ សាន"
    assert data.full_name_english == "SOK SAN"
    assert data.gender == "ប្រុស"
    assert "2000-04-15" in str(data.date_of_birth)
    assert data.place_of_birth == "រាជធានីភ្នំពេញ"
    assert data.father_name == "សុខ មករា"
    assert data.mother_name == "កែវ ធីតា"
    assert "1234/2000" in str(data.registration_number)


def test_missing_fields_return_null_strictly():
    """
    Verify strict requirement:
    Never invent missing information. Return null for unavailable fields.
    """
    minimal_text = """
    សេចក្តីចម្លងសំបុត្រកំណើត
    ឈ្មោះ : ឡុង វិបុល
    ភេទ : ប្រុស
    """
    data = birth_certificate_extractor.extract(minimal_text)

    assert data.full_name_khmer == "ឡុង វិបុល"
    assert data.gender == "ប្រុស"
    # All absent fields MUST be None (null)
    assert data.full_name_english is None
    assert data.father_name is None
    assert data.mother_name is None
    assert data.place_of_birth is None
    assert data.registration_number is None
    assert data.date_of_birth is None
