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
    edited_text: Optional[str] = None
    average_confidence: Optional[float]
    birth_certificate_data: Optional[BirthCertificateData] = None
    government_entities: Optional[Dict[str, Any]] = None
    layout_detected: bool = False
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
    has_edited_text: bool = False
    has_docx: bool = False
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    total: int
    items: List[DocumentMetadataResponse]
