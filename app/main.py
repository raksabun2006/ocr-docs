"""
Khmer Government Document Intelligence System
Pure Backend API Entrypoint

FastAPI REST backend with OpenCV image preprocessing, Tesseract OCR (khm+eng),
document classification, structured data extraction, human verification workflow,
search archive, and tamper-resistant audit logging.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.services.ocr_service import ocr_service
from app.services.file_validator import FileValidationError, FileTooLargeError
from app.services.image_service import ImageProcessingError
from app.services.ocr_service import OCRError
from app.services.verification_service import VerificationError

from app.routers.document_router import router as document_router
from app.routers.verification_router import router as verification_router
from app.routers.classification_router import router as classification_router
from app.routers.search_router import router as search_router
from app.routers.audit_router import router as audit_router
from app.routers.receipt_router import router as receipt_router

# Configure Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Initializing Khmer Government Document Intelligence Backend...")
    # 1. Initialize Database Schema
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error(f"Database initialization error: {exc}")

    # 2. Check OCR Environment
    ocr_env = ocr_service.verify_environment()
    if ocr_env["ready_for_ocr"]:
        logger.info(
            f"Tesseract OCR is ready with models: {', '.join(ocr_env['languages_found'])}"
        )
    else:
        logger.warning(
            f"Tesseract OCR environment check: installed={ocr_env['tesseract_installed']}, "
            f"eng={ocr_env['has_english']}, khm={ocr_env['has_khmer']}. "
            f"Data dir: {ocr_env['tessdata_dir']}"
        )

    yield

    logger.info("Shutting down Khmer Government Document Intelligence Backend.")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Production-ready pure REST API for Khmer Government Document Intelligence System. "
        "Digitizes, recognizes (Khmer + English OCR), classifies, and archives Cambodian "
        "administrative documents (Birth Certificates, Family Books, IDs, Letters, Forms, Receipts)."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware for external frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Security Exception Handlers (Prevent stack trace or internal path leaks)
@app.exception_handler(FileValidationError)
async def file_validation_exception_handler(request: Request, exc: FileValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"success": False, "error": "Invalid Document", "detail": str(exc)}
    )


@app.exception_handler(FileTooLargeError)
async def file_too_large_exception_handler(request: Request, exc: FileTooLargeError):
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={"success": False, "error": "File Too Large", "detail": str(exc)}
    )


@app.exception_handler(ImageProcessingError)
async def image_processing_exception_handler(request: Request, exc: ImageProcessingError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, "error": "Processing Failed", "detail": "The document image could not be processed."}
    )


@app.exception_handler(OCRError)
async def ocr_exception_handler(request: Request, exc: OCRError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "error": "OCR Failure", "detail": "Text recognition service encountered an error."}
    )


@app.exception_handler(VerificationError)
async def verification_exception_handler(request: Request, exc: VerificationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"success": False, "error": "Verification Error", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error: {exc}", exc_info=False)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "error": "Internal Error", "detail": "An internal server error occurred."}
    )


# Register API v1 Routers
api_prefix = settings.API_V1_STR
app.include_router(document_router, prefix=api_prefix)
app.include_router(verification_router, prefix=api_prefix)
app.include_router(classification_router, prefix=api_prefix)
app.include_router(search_router, prefix=api_prefix)
app.include_router(audit_router, prefix=api_prefix)
app.include_router(receipt_router, prefix=api_prefix)


@app.get("/", tags=["Health & Status"])
@app.get("/api/v1/health", tags=["Health & Status"])
def health_status():
    """Returns backend system status, OCR engine health, and API documentation URLs."""
    ocr_env = ocr_service.verify_environment()
    return {
        "system": settings.APP_NAME,
        "version": "1.0.0",
        "status": "online",
        "ocr_engine": {
            "ready": ocr_env["ready_for_ocr"],
            "languages": ocr_env["languages_found"]
        },
        "docs_url": "/docs",
        "openapi_url": "/openapi.json"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
