"""
Human Verification Service
Khmer Government Document Intelligence System

Enforces verification workflow:
- Highlights uncertain OCR extractions for Cambodian administrative officers.
- Requires explicit confirmation before finalizing verified records.
- Logs all modifications to VerificationHistory and AuditLog.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models import Document, ExtractedField, VerificationHistory
from app.schemas.verification import (
    DocumentVerificationView,
    FieldVerificationDetail,
    VerificationHistoryItem,
    VerificationSubmissionRequest,
    VerificationSubmissionResponse
)
from app.services.audit_service import audit_service


class VerificationError(Exception):
    """Raised when verification workflow fails validation."""
    pass


class VerificationService:
    """Handles officer verification, correction tracking, and finalization."""

    def get_document_for_verification(self, db: Session, document_id: str) -> DocumentVerificationView:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise VerificationError(f"Document with ID '{document_id}' not found.")

        # Gather extracted fields
        field_records = db.query(ExtractedField).filter(ExtractedField.document_id == document_id).all()
        fields_view = []
        highlighted_uncertain = []

        for f in field_records:
            conf = f.confidence or 0.0
            uncertainty = "low_uncertainty"
            if conf < 50.0:
                uncertainty = "high_uncertainty"
                highlighted_uncertain.append(f.field_name)
            elif conf < 80.0:
                uncertainty = "medium_uncertainty"
                highlighted_uncertain.append(f.field_name)

            fields_view.append(FieldVerificationDetail(
                field_name=f.field_name,
                field_value=f.field_value,
                confidence=f.confidence,
                uncertainty_level=uncertainty,
                bounding_box=f.bounding_box,
                is_verified=f.is_verified
            ))

        # Gather verification history
        hist_records = (
            db.query(VerificationHistory)
            .filter(VerificationHistory.document_id == document_id)
            .order_by(VerificationHistory.verified_at.desc())
            .all()
        )
        history_view = [
            VerificationHistoryItem(
                field_name=h.field_name,
                original_value=h.original_value,
                corrected_value=h.corrected_value,
                verified_by=h.verified_by,
                notes=h.notes,
                verified_at=h.verified_at
            ) for h in hist_records
        ]

        document_url = f"/api/v1/documents/{document.id}/file"

        return DocumentVerificationView(
            document_id=document.id,
            original_filename=document.original_filename,
            document_type=document.document_type,
            status=document.status,
            document_file_url=document_url,
            average_confidence=document.average_confidence,
            highlighted_uncertain_fields=highlighted_uncertain,
            fields=fields_view,
            history=history_view
        )

    def submit_verification(
        self,
        db: Session,
        document_id: str,
        request: VerificationSubmissionRequest,
        ip_address: str = "127.0.0.1"
    ) -> VerificationSubmissionResponse:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise VerificationError(f"Document with ID '{document_id}' not found.")

        if not request.confirm_and_finalize:
            raise VerificationError("Official confirmation is mandatory before saving verified records.")

        corrections_applied = 0
        now = datetime.now(timezone.utc)

        # Apply field corrections
        for corr in request.corrections:
            field_rec = (
                db.query(ExtractedField)
                .filter(
                    ExtractedField.document_id == document_id,
                    ExtractedField.field_name == corr.field_name
                )
                .first()
            )

            old_val = field_rec.field_value if field_rec else None

            # Only record if there is a real modification or newly set
            if not field_rec or field_rec.field_value != corr.corrected_value:
                if field_rec:
                    field_rec.field_value = corr.corrected_value
                    field_rec.is_verified = True
                    field_rec.updated_at = now
                else:
                    field_rec = ExtractedField(
                        document_id=document_id,
                        field_name=corr.field_name,
                        field_value=corr.corrected_value,
                        confidence=100.0,
                        is_verified=True,
                        created_at=now,
                        updated_at=now
                    )
                    db.add(field_rec)

                # Save history
                history_entry = VerificationHistory(
                    document_id=document_id,
                    field_name=corr.field_name,
                    original_value=old_val,
                    corrected_value=corr.corrected_value,
                    verified_by=request.reviewer_name,
                    notes=corr.notes or request.notes,
                    verified_at=now
                )
                db.add(history_entry)
                corrections_applied += 1

        # Mark all existing fields of this document as verified
        db.query(ExtractedField).filter(
            ExtractedField.document_id == document_id
        ).update({"is_verified": True, "updated_at": now})

        # Update document status to VERIFIED
        document.status = "VERIFIED"
        document.updated_at = now
        db.commit()

        # Audit log (without sensitive personal details)
        audit_service.log_action(
            db=db,
            user_id=request.reviewer_name,
            action="VERIFY",
            resource_type="DOCUMENT",
            resource_id=document_id,
            ip_address=ip_address,
            details={
                "corrections_count": corrections_applied,
                "status_transition": "VERIFIED",
                "notes": request.notes
            }
        )

        return VerificationSubmissionResponse(
            success=True,
            document_id=document.id,
            status=document.status,
            message="Document successfully reviewed, verified, and officially finalized.",
            total_corrected_fields=corrections_applied,
            verified_by=request.reviewer_name,
            verified_at=now
        )


verification_service = VerificationService()
