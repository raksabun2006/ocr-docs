"""
Document Classification Router
Khmer Government Document Intelligence System
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document
from app.schemas.classification import (
    ClassificationResult,
    ClassificationCorrectionRequest,
    DOCUMENT_TYPE_LABELS
)
from app.services.classifier_service import classifier_service
from app.services.audit_service import audit_service

router = APIRouter(prefix="/classification", tags=["Classification"])


@router.get("/{document_id}", response_model=ClassificationResult)
def reclassify_document(document_id: str, db: Session = Depends(get_db)):
    """Re-runs automated classification based on document's extracted OCR text."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    res = classifier_service.classify_text(doc.raw_text or "")
    return res


@router.patch("/{document_id}/override", status_code=status.HTTP_200_OK)
def override_document_classification(
    document_id: str,
    request: ClassificationCorrectionRequest,
    officer_name: str = "officer",
    db: Session = Depends(get_db)
):
    """
    Allows authorized public-sector officials to manually correct/override
    the document classification type.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    old_type = doc.document_type
    doc.document_type = request.document_type.value
    doc.is_classified_by_user = True
    db.commit()

    # Log reclassification audit
    audit_service.log_action(
        db=db,
        user_id=officer_name,
        action="CLASSIFY",
        resource_type="DOCUMENT",
        resource_id=document_id,
        details={
            "old_type": old_type,
            "new_type": request.document_type.value,
            "reason": request.reason
        }
    )

    return {
        "success": True,
        "document_id": document_id,
        "old_type": old_type,
        "new_type": request.document_type.value,
        "new_type_khmer": DOCUMENT_TYPE_LABELS.get(request.document_type, "Unknown"),
        "is_classified_by_user": True
    }
