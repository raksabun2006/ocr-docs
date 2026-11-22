"""
Document Management and OCR Router
Khmer Government Document Intelligence System
"""

import os
import hashlib
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Document, ExtractedField
from app.schemas.document import DocumentUploadResponse, DocumentMetadataResponse
from app.schemas.classification import DOCUMENT_TYPE_LABELS, DocumentTypeEnum
from app.services.file_validator import (
    validate_document_content,
    generate_secure_storage_path,
    sanitize_filename,
    FileValidationError,
    FileTooLargeError
)
from app.services.image_service import (
    preprocess_for_ocr,
    convert_pdf_to_images,
    generate_multi_representation_variants,
    ImageProcessingError
)
from app.services.ocr_service import ocr_service, OCRError
from app.services.classifier_service import classifier_service
from app.services.extraction_service import birth_certificate_extractor
from app.services.audit_service import audit_service

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_and_process_document(
    file: UploadFile = File(..., description="Document file (JPG, PNG, or PDF up to 15MB)"),
    officer_name: str = Form("officer", description="Name/ID of uploading official"),
    db: Session = Depends(get_db)
):
    """
    Securely uploads a Cambodian government document:
    1. Validates magic bytes, size limit, and file integrity.
    2. Stores in isolated, UUID-hashed storage.
    3. Preprocesses with OpenCV (deskew, CLAHE contrast enhancement, noise filter, binarization).
    4. Executes OCR in Khmer and English (khm+eng).
    5. Performs automated classification into official categories.
    6. If classified as a Birth Certificate, automatically extracts structured civil registration fields.
    7. Creates audit log.
    """
    # 1. Read file bytes safely
    try:
        file_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to read uploaded file.")

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing filename.")

    # 2. Validation
    try:
        mime_type, ext = validate_document_content(file_bytes, file.filename)
    except FileTooLargeError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except FileValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 3. Secure storage path
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    doc_id, storage_path = generate_secure_storage_path(ext)

    try:
        with open(storage_path, "wb") as f:
            f.write(file_bytes)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store document file safely.")

    # 4. Image Preprocessing & OCR
    raw_text = ""
    avg_confidence = 0.0
    structured_ocr_data = None

    try:
        if mime_type == "application/pdf":
            # Convert first page of PDF for OCR
            pdf_pages = convert_pdf_to_images(file_bytes, max_pages=1)
            import cv2
            success, enc = cv2.imencode(".png", pdf_pages[0])
            if not success:
                raise ImageProcessingError("Failed to encode PDF raster.")
            img_input_bytes = enc.tobytes()
        else:
            img_input_bytes = file_bytes

        # Adaptive multi-representation preprocessing and multi-PSM OCR
        variants = generate_multi_representation_variants(img_input_bytes)
        raw_text, structured_ocr_data = ocr_service.process_document_adaptive(
            variants,
            languages=settings.OCR_DEFAULT_LANGUAGES
        )
        avg_confidence = structured_ocr_data.get("average_confidence", 0.0)
    except (ImageProcessingError, OCRError) as err:
        # Gracefully preserve document record even if scan is blank/corrupt
        raw_text = f"[OCR Warning]: {str(err)}"
        avg_confidence = 0.0

    # 5. Document Classification
    classification = classifier_service.classify_text(raw_text)
    detected_type = classification.document_type.value

    # 6. Structured Information Extraction (e.g. Birth Certificate)
    bc_data = None
    if detected_type == DocumentTypeEnum.BIRTH_CERTIFICATE.value:
        bc_data = birth_certificate_extractor.extract(raw_text, structured_ocr_data)

    # 7. Persist to Database
    safe_orig_filename = sanitize_filename(file.filename)
    new_doc = Document(
        id=doc_id,
        original_filename=safe_orig_filename,
        storage_path=str(storage_path),
        mime_type=mime_type,
        file_size_bytes=len(file_bytes),
        sha256_hash=sha256_hash,
        document_type=detected_type,
        is_classified_by_user=False,
        status="PROCESSED" if raw_text else "PENDING",
        raw_text=raw_text,
        average_confidence=avg_confidence,
        uploaded_by=officer_name
    )
    db.add(new_doc)
    db.flush()

    # Save extracted fields to database
    if bc_data:
        fields_map = {
            "full_name_khmer": bc_data.full_name_khmer,
            "full_name_english": bc_data.full_name_english,
            "date_of_birth": bc_data.date_of_birth,
            "gender": bc_data.gender,
            "place_of_birth": bc_data.place_of_birth,
            "father_name": bc_data.father_name,
            "mother_name": bc_data.mother_name,
            "registration_number": bc_data.registration_number,
            "registration_date": bc_data.registration_date,
        }
        for fname, fval in fields_map.items():
            if fval is not None:
                field_conf_obj = bc_data.field_confidences.get(fname)
                conf_score = field_conf_obj.confidence if field_conf_obj else avg_confidence
                db_field = ExtractedField(
                    document_id=doc_id,
                    field_name=fname,
                    field_value=fval,
                    confidence=conf_score,
                    is_verified=False
                )
                db.add(db_field)

    db.commit()
    db.refresh(new_doc)

    # 8. Audit Log
    audit_service.log_action(
        db=db,
        user_id=officer_name,
        action="UPLOAD",
        resource_type="DOCUMENT",
        resource_id=doc_id,
        details={
            "filename": safe_orig_filename,
            "file_size": len(file_bytes),
            "mime_type": mime_type,
            "detected_type": detected_type
        }
    )

    khmer_label = DOCUMENT_TYPE_LABELS.get(classification.document_type, "ឯកសារទូទៅ")

    return DocumentUploadResponse(
        document_id=new_doc.id,
        original_filename=new_doc.original_filename,
        mime_type=new_doc.mime_type,
        file_size_bytes=new_doc.file_size_bytes,
        sha256_hash=new_doc.sha256_hash,
        document_type=new_doc.document_type,
        type_khmer_label=khmer_label,
        status=new_doc.status,
        extracted_text=new_doc.raw_text,
        average_confidence=new_doc.average_confidence,
        birth_certificate_data=bc_data,
        created_at=new_doc.created_at
    )


@router.get("/{document_id}", response_model=DocumentMetadataResponse)
def get_document_details(document_id: str, db: Session = Depends(get_db)):
    """Retrieves document metadata by ID."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    return DocumentMetadataResponse(
        document_id=doc.id,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        sha256_hash=doc.sha256_hash,
        document_type=doc.document_type,
        status=doc.status,
        average_confidence=doc.average_confidence,
        created_at=doc.created_at,
        updated_at=doc.updated_at
    )


@router.get("/{document_id}/file")
def get_document_file(document_id: str, db: Session = Depends(get_db)):
    """
    Secure file retrieval endpoint for human verification interface.
    Serves the original document image or PDF.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored document file not found on disk.")

    audit_service.log_action(
        db=db,
        user_id="officer",
        action="VIEW",
        resource_type="DOCUMENT",
        resource_id=document_id
    )

    return FileResponse(
        path=doc.storage_path,
        media_type=doc.mime_type,
        filename=doc.original_filename
    )


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(document_id: str, officer_name: str = "admin", db: Session = Depends(get_db)):
    """Deletes document file and associated database records with audit trail."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # Remove file from disk
    if os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except OSError:
            pass

    # Audit logging
    audit_service.log_action(
        db=db,
        user_id=officer_name,
        action="DELETE",
        resource_type="DOCUMENT",
        resource_id=document_id
    )

    db.delete(doc)
    db.commit()
    return {"success": True, "message": f"Document {document_id} successfully deleted."}
