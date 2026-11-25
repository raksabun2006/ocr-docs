"""
Classification Schemas
Khmer Government Document Intelligence System
"""

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class DocumentTypeEnum(str, Enum):
    # Specialized Government Administrative Documents
    ADMINISTRATIVE_LETTER = "ADMINISTRATIVE_LETTER"  # លិខិតរដ្ឋបាល
    INVITATION_LETTER = "INVITATION_LETTER"          # លិខិតអញ្ជើញ
    REQUEST_LETTER = "REQUEST_LETTER"                # លិខិតស្នើសុំ / ពាក្យស្នើសុំ
    ANNOUNCEMENT_NOTICE = "ANNOUNCEMENT_NOTICE"      # សេចក្តីជូនដំណឹង
    DECISION = "DECISION"                            # សេចក្តីសម្រេច
    REPORT = "REPORT"                                # របាយការណ៍
    ATTESTATION_LETTER = "ATTESTATION_LETTER"        # លិខិតបញ្ជាក់
    APPLICATION_FORM = "APPLICATION_FORM"            # ពាក្យសុំ / ទម្រង់បែបបទ
    OFFICIAL_CERTIFICATE = "OFFICIAL_CERTIFICATE"    # វិញ្ញាបនបត្រ / សញ្ញាបត្រ

    # Civil Registration & Identification
    BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE"          # សំបុត្រកំណើត
    FAMILY_BOOK = "FAMILY_BOOK"                      # សៀវភៅគ្រួសារ
    IDENTITY_CARD = "IDENTITY_CARD"                  # អត្តសញ្ញាណប័ណ្ណ

    # Receipts & Miscellaneous
    OFFICIAL_RECEIPT = "OFFICIAL_RECEIPT"            # បង្កាន់ដៃ / វិក្កយបត្រ
    UNKNOWN = "UNKNOWN"                              # ឯកសារទូទៅ / មិនទាន់កំណត់ប្រភេទ


DOCUMENT_TYPE_LABELS = {
    DocumentTypeEnum.ADMINISTRATIVE_LETTER: "លិខិតរដ្ឋបាល (Administrative Letter)",
    DocumentTypeEnum.INVITATION_LETTER: "លិខិតអញ្ជើញ (Invitation Letter)",
    DocumentTypeEnum.REQUEST_LETTER: "លិខិតស្នើសុំ / ពាក្យស្នើសុំ (Request Letter)",
    DocumentTypeEnum.ANNOUNCEMENT_NOTICE: "សេចក្តីជូនដំណឹង (Announcement / Notice)",
    DocumentTypeEnum.DECISION: "សេចក្តីសម្រេច (Decision)",
    DocumentTypeEnum.REPORT: "របាយការណ៍ (Report)",
    DocumentTypeEnum.ATTESTATION_LETTER: "លិខិតបញ្ជាក់ (Attestation / Certificate)",
    DocumentTypeEnum.APPLICATION_FORM: "ពាក្យស្នើសុំ / ពាក្យសុំ (Application Form)",
    DocumentTypeEnum.OFFICIAL_CERTIFICATE: "វិញ្ញាបនបត្រ / សញ្ញាបត្រ (Official Certificate)",
    DocumentTypeEnum.BIRTH_CERTIFICATE: "សំបុត្រកំណើត (Birth Certificate)",
    DocumentTypeEnum.FAMILY_BOOK: "សៀវភៅគ្រួសារ (Family Book)",
    DocumentTypeEnum.IDENTITY_CARD: "អត្តសញ្ញាណប័ណ្ណ (Identity Card)",
    DocumentTypeEnum.OFFICIAL_RECEIPT: "បង្កាន់ដៃ / វិក្កយបត្រ (Official Receipt)",
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
