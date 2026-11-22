"""
Human Verification Schemas
Khmer Government Document Intelligence System
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class FieldVerificationDetail(BaseModel):
    field_name: str
    field_value: Optional[str]
    confidence: Optional[float]
    uncertainty_level: str  # high_uncertainty, medium_uncertainty, low_uncertainty
    bounding_box: Optional[Dict[str, int]]
    is_verified: bool


class VerificationHistoryItem(BaseModel):
    field_name: str
    original_value: Optional[str]
    corrected_value: Optional[str]
    verified_by: str
    notes: Optional[str]
    verified_at: datetime


class DocumentVerificationView(BaseModel):
    document_id: str
    original_filename: str
    document_type: str
    status: str
    document_file_url: str
    average_confidence: Optional[float]
    highlighted_uncertain_fields: List[str]
    fields: List[FieldVerificationDetail]
    history: List[VerificationHistoryItem]


class FieldCorrectionInput(BaseModel):
    field_name: str
    corrected_value: str
    notes: Optional[str] = None


class VerificationSubmissionRequest(BaseModel):
    reviewer_name: str = Field(..., min_length=2, max_length=100)
    corrections: List[FieldCorrectionInput] = Field(default_factory=list)
    confirm_and_finalize: bool = Field(
        ...,
        description="Explicit official confirmation required to finalize verified record."
    )
    notes: Optional[str] = None


class VerificationSubmissionResponse(BaseModel):
    success: bool
    document_id: str
    status: str
    message: str
    total_corrected_fields: int
    verified_by: str
    verified_at: datetime
