"""
Classification Schemas
Khmer Government Document Intelligence System
"""

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class DocumentTypeEnum(str, Enum):
    BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE"        # សំបុត្រកំណើត
    FAMILY_BOOK = "FAMILY_BOOK"                    # សៀវភៅគ្រួសារ
    IDENTITY_CARD = "IDENTITY_CARD"                # អត្តសញ្ញាណប័ណ្ណ
    ADMINISTRATIVE_LETTER = "ADMINISTRATIVE_LETTER"# លិខិតរដ្ឋបាល
    APPLICATION_FORM = "APPLICATION_FORM"          # ពាក្យសុំ / ពាក្យស្នើសុំ
    OFFICIAL_CERTIFICATE = "OFFICIAL_CERTIFICATE"  # វិញ្ញាបនបត្រ / សញ្ញាបត្រ
    UNKNOWN = "UNKNOWN"                            # មិនស្គាល់


DOCUMENT_TYPE_LABELS = {
    DocumentTypeEnum.BIRTH_CERTIFICATE: "សំបុត្រកំណើត (Birth Certificate)",
    DocumentTypeEnum.FAMILY_BOOK: "សៀវភៅគ្រួសារ (Family Book)",
    DocumentTypeEnum.IDENTITY_CARD: "អត្តសញ្ញាណប័ណ្ណ (Identity Card)",
    DocumentTypeEnum.ADMINISTRATIVE_LETTER: "លិខិតរដ្ឋបាល (Administrative Letter)",
    DocumentTypeEnum.APPLICATION_FORM: "ពាក្យស្នើសុំ / ពាក្យសុំ (Application Form)",
    DocumentTypeEnum.OFFICIAL_CERTIFICATE: "វិញ្ញាបនបត្រ / សញ្ញាបត្រ (Official Certificate)",
    DocumentTypeEnum.UNKNOWN: "ឯកសារទូទៅ / មិនទាន់កំណត់ប្រភេទ (Unknown / Unclassified)"
}


class ClassificationResult(BaseModel):
    document_type: DocumentTypeEnum
    type_khmer_label: str
    confidence: float
    matched_keywords: List[str]
    scores: Dict[str, float]


class ClassificationCorrectionRequest(BaseModel):
    document_type: DocumentTypeEnum = Field(..., description="Corrected official document type")
    reason: Optional[str] = Field(None, description="Reason or remarks for manual reclassification")
