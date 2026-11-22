"""
Birth Certificate Schema (សំបុត្រកំណើត)
Khmer Government Document Intelligence System

Structured schema for Cambodian birth civil registration certificates.
Strictly returns null for fields not clearly present in the document.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class BirthCertificateField(BaseModel):
    """Represents an extracted field with value, confidence, and uncertainty indicator."""
    value: Optional[str] = None
    confidence: Optional[float] = None
    uncertainty_level: str = "high_uncertainty"  # low_uncertainty, medium_uncertainty, high_uncertainty


class BirthCertificateData(BaseModel):
    """
    Standardized Cambodian Birth Certificate extracted data model.
    Fields without confident extraction default to null (None).
    """
    full_name_khmer: Optional[str] = Field(
        default=None,
        description="គោត្តនាម និង នាម (Full name in Khmer script)"
    )
    full_name_english: Optional[str] = Field(
        default=None,
        description="Latin Name (Full name in English / Latin alphabet)"
    )
    date_of_birth: Optional[str] = Field(
        default=None,
        description="ថ្ងៃ ខែ ឆ្នាំ កំណើត (Standardized date of birth YYYY-MM-DD or raw representation)"
    )
    gender: Optional[str] = Field(
        default=None,
        description="ភេទ (ប្រុស / ស្រី, Male / Female)"
    )
    place_of_birth: Optional[str] = Field(
        default=None,
        description="ទីកន្លែងកំណើត (Village, Commune, District, Province/Capital)"
    )
    father_name: Optional[str] = Field(
        default=None,
        description="ឪពុកឈ្មោះ (Father's full name)"
    )
    mother_name: Optional[str] = Field(
        default=None,
        description="ម្តាយឈ្មោះ (Mother's full name)"
    )
    registration_number: Optional[str] = Field(
        default=None,
        description="លេខសំបុត្រ / លេខចុះបញ្ជី (Civil registration certificate number)"
    )
    registration_date: Optional[str] = Field(
        default=None,
        description="ថ្ងៃចុះបញ្ជី (Registration date)"
    )

    field_confidences: Dict[str, BirthCertificateField] = Field(
        default_factory=dict,
        description="Field-level extraction confidence and uncertainty status"
    )
    raw_text: Optional[str] = Field(
        default=None,
        description="Full raw OCR text extracted from the certificate"
    )
