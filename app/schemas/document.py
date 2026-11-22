"""
Document Schemas
Khmer Government Document Intelligence System
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.classification import DocumentTypeEnum
from app.schemas.birth_certificate import BirthCertificateData


class DocumentUploadResponse(BaseModel):
    document_id: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    document_type: str
    type_khmer_label: str
    status: str
    extracted_text: Optional[str]
    average_confidence: Optional[float]
    birth_certificate_data: Optional[BirthCertificateData] = None
    created_at: datetime


class DocumentMetadataResponse(BaseModel):
    document_id: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    document_type: str
    status: str
    average_confidence: Optional[float]
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    total: int
    items: List[DocumentMetadataResponse]
