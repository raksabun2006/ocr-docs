"""
Human Verification Router
Khmer Government Document Intelligence System
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.verification import (
    DocumentVerificationView,
    VerificationSubmissionRequest,
    VerificationSubmissionResponse
)
from app.services.verification_service import verification_service, VerificationError

router = APIRouter(prefix="/verifications", tags=["Human Verification"])


@router.get("/{document_id}", response_model=DocumentVerificationView)
def get_verification_workspace(document_id: str, db: Session = Depends(get_db)):
    """
    Returns side-by-side verification payload:
    - Original document access link.
    - Extracted fields.
    - Highlighted low-confidence / uncertain OCR fields.
    - Prior correction history.
    """
    try:
        return verification_service.get_document_for_verification(db, document_id)
    except VerificationError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.post("/{document_id}/submit", response_model=VerificationSubmissionResponse)
def submit_verification_corrections(
    document_id: str,
    request_data: VerificationSubmissionRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Applies human reviewer corrections to extracted fields.
    Requires explicit official confirmation (confirm_and_finalize=True) to finalize the verified record.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        return verification_service.submit_verification(
            db=db,
            document_id=document_id,
            request=request_data,
            ip_address=client_ip
        )
    except VerificationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
