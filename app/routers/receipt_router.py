"""
Receipt Scan Compatibility Router
Khmer Government Document Intelligence System

Maintains backward-compatibility for receipt scanning endpoints
under `/api/v1/receipts/scan` using the unified OpenCV & Tesseract engine.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from pydantic import BaseModel
from typing import List

from app.config import settings
from app.services.file_validator import validate_document_content, FileValidationError, FileTooLargeError
from app.services.image_service import preprocess_for_ocr, ImageProcessingError
from app.services.ocr_service import ocr_service, OCRError

router = APIRouter(prefix="/receipts", tags=["Receipts Compatibility"])


class ScanReceiptResponse(BaseModel):
    success: bool
    filename: str
    languages: List[str]
    extracted_text: str


@router.post("/scan", response_model=ScanReceiptResponse)
async def scan_receipt(
    file: UploadFile = File(..., description="Uploaded receipt image (JPG or PNG)")
):
    """
    Scans a receipt image in English and Khmer:
    POST /api/v1/receipts/scan
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing filename.")

    try:
        file_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to read file.")

    # 1. Validate
    try:
        mime_type, ext = validate_document_content(file_bytes, file.filename)
        if ext.lower() not in (".jpg", ".jpeg", ".png"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only JPG and PNG formats are accepted for receipt scans. Provided: {ext}"
            )
    except FileTooLargeError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except FileValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 2. Preprocess & OCR
    try:
        preprocessed = preprocess_for_ocr(file_bytes)
        text = ocr_service.extract_text(preprocessed, languages=settings.OCR_DEFAULT_LANGUAGES)
    except (ImageProcessingError, OCRError) as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="OCR processing error.")

    return ScanReceiptResponse(
        success=True,
        filename=file.filename,
        languages=["eng", "khm"],
        extracted_text=text
    )
