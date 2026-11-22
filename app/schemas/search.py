"""
Search and Digital Archive Schemas
Khmer Government Document Intelligence System
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.document import DocumentMetadataResponse


class DocumentSearchQuery(BaseModel):
    query: Optional[str] = Field(None, description="Free text keyword or person name (Khmer/English)")
    document_type: Optional[str] = Field(None, description="Filter by official document type")
    status: Optional[str] = Field(None, description="Filter by status (PENDING, PROCESSED, VERIFIED, REJECTED)")
    registration_number: Optional[str] = Field(None, description="Filter by registration or certificate number")
    from_date: Optional[datetime] = Field(None, description="Created on or after date")
    to_date: Optional[datetime] = Field(None, description="Created on or before date")
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)


class DocumentSearchResult(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int
    items: List[DocumentMetadataResponse]
