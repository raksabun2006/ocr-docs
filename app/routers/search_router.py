"""
Search and Digital Archive Router
Khmer Government Document Intelligence System
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Document, ExtractedField
from app.schemas.search import DocumentSearchResult
from app.schemas.document import DocumentMetadataResponse

router = APIRouter(prefix="/archive", tags=["Digital Archive"])


@router.get("/search", response_model=DocumentSearchResult)
def search_digital_archive(
    query: Optional[str] = Query(None, description="Keyword or person name in Khmer/English"),
    document_type: Optional[str] = Query(None, description="Document type filter"),
    status: Optional[str] = Query(None, description="Status filter"),
    registration_number: Optional[str] = Query(None, description="Registration number"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Searches the digital government document archive:
    - Full-text search across raw OCR text.
    - Matches citizen names or extracted fields.
    - Filters by document type, registration number, or verification status.
    """
    base_query = db.query(Document)

    if document_type:
        base_query = base_query.filter(Document.document_type == document_type.upper())

    if status:
        base_query = base_query.filter(Document.status == status.upper())

    if registration_number:
        # Search extracted fields for registration number
        matching_doc_ids = (
            db.query(ExtractedField.document_id)
            .filter(
                ExtractedField.field_name.in_(["registration_number", "id_number"]),
                ExtractedField.field_value.ilike(f"%{registration_number}%")
            )
            .subquery()
        )
        base_query = base_query.filter(Document.id.in_(matching_doc_ids))

    if query and query.strip():
        search_term = f"%{query.strip()}%"
        # Match against raw_text, original_filename, or any extracted_field value
        matching_field_docs = (
            db.query(ExtractedField.document_id)
            .filter(ExtractedField.field_value.ilike(search_term))
            .subquery()
        )
        base_query = base_query.filter(
            or_(
                Document.raw_text.ilike(search_term),
                Document.original_filename.ilike(search_term),
                Document.id.in_(matching_field_docs)
            )
        )

    total_count = base_query.count()
    offset = (page - 1) * limit
    results = base_query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()

    items = [
        DocumentMetadataResponse(
            document_id=d.id,
            original_filename=d.original_filename,
            mime_type=d.mime_type,
            file_size_bytes=d.file_size_bytes,
            sha256_hash=d.sha256_hash,
            document_type=d.document_type,
            status=d.status,
            average_confidence=d.average_confidence,
            created_at=d.created_at,
            updated_at=d.updated_at
        )
        for d in results
    ]

    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    return DocumentSearchResult(
        total=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages,
        items=items
    )
