"""
File Validation and Security Service
Khmer Government Document Intelligence System

Enforces secure file handling:
- Magic byte validation.
- File size enforcement.
- Safe content inspection (PIL / PDF structure).
- Path traversal defense and UUID-based secure storage paths.
"""

import io
import os
import uuid
import re
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image, UnidentifiedImageError

from app.config import settings


class FileValidationError(Exception):
    """Raised when an uploaded document fails security or format validation."""
    pass


class FileTooLargeError(FileValidationError):
    """Raised when an uploaded document exceeds the allowed size limit."""
    pass


# Magic byte signatures
MAGIC_BYTES = {
    "jpeg": b"\xFF\xD8\xFF",
    "png": b"\x89PNG\r\n\x1a\n",
    "pdf": b"%PDF-",
}


def sanitize_filename(filename: str) -> str:
    """Strip dangerous characters and path traversal patterns from filenames."""
    basename = os.path.basename(filename)
    # Remove any non-alphanumeric, dot, dash, or underscore characters
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "_", basename)
    return sanitized or "document"


def detect_file_type_by_magic_bytes(file_bytes: bytes) -> Optional[str]:
    """Detect actual file type using byte signatures."""
    if len(file_bytes) < 8:
        return None
    if file_bytes.startswith(MAGIC_BYTES["jpeg"]):
        return "image/jpeg"
    if file_bytes.startswith(MAGIC_BYTES["png"]):
        return "image/png"
    if file_bytes.startswith(MAGIC_BYTES["pdf"]):
        return "application/pdf"
    return None


def validate_document_content(file_bytes: bytes, filename: str) -> Tuple[str, str]:
    """
    Validates the uploaded document:
    1. Size limit.
    2. Extension whitelist.
    3. Magic byte signature match.
    4. Internal structure validity (PIL verification for images, PDF structural check).

    Returns:
        Tuple[str, str]: (detected_mime_type, file_extension)
    Raises:
        FileValidationError / FileTooLargeError
    """
    if not file_bytes:
        raise FileValidationError("Uploaded file is empty.")

    # 1. Size Check
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise FileTooLargeError(
            f"File size ({len(file_bytes) / (1024 * 1024):.2f} MB) exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    # 2. Extension Check
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"File extension '{ext}' is not permitted. Allowed: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}"
        )

    # 3. Magic Byte Detection
    detected_mime = detect_file_type_by_magic_bytes(file_bytes)
    if not detected_mime or detected_mime not in settings.ALLOWED_MIME_TYPES:
        raise FileValidationError(
            "File content signature does not match an allowed format (JPG, PNG, PDF)."
        )

    # 4. Deep Content Verification
    if detected_mime in ("image/jpeg", "image/png"):
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                img.verify()  # Verifies file integrity without decoding full raster
                format_name = (img.format or "").upper()
                if detected_mime == "image/jpeg" and format_name != "JPEG":
                    raise FileValidationError("Image content does not match JPEG specifications.")
                if detected_mime == "image/png" and format_name != "PNG":
                    raise FileValidationError("Image content does not match PNG specifications.")
                
                # Check dimensions
                width, height = img.size
                if width <= 0 or height <= 0:
                    raise FileValidationError("Invalid image dimensions.")
                if width > 15000 or height > 15000:
                    raise FileValidationError("Image dimensions exceed maximum processing bounds.")
        except (UnidentifiedImageError, OSError, Exception) as exc:
            raise FileValidationError(f"Corrupted or malformed image document: {str(exc)}")

    elif detected_mime == "application/pdf":
        # Check PDF header and minimum content length
        if len(file_bytes) < 32 or b"%PDF-" not in file_bytes[:1024]:
            raise FileValidationError("Invalid PDF document structure.")
        # Ensure it contains EOF marker somewhere in the last 2048 bytes
        tail = file_bytes[-2048:]
        if b"%%EOF" not in tail and b"xref" not in tail and b"startxref" not in tail:
            # Some stream-based PDFs might not strictly end with %%EOF, but check basic PDF object syntax
            if b"obj" not in file_bytes:
                raise FileValidationError("Malformed or truncated PDF document.")

    return detected_mime, ext


def generate_secure_storage_path(extension: str) -> Tuple[str, Path]:
    """
    Generates a unique, collision-proof storage filename and path.
    Prevents path traversal by isolating all uploads within the configured UPLOAD_DIR.
    """
    unique_id = str(uuid.uuid4())
    safe_filename = f"{unique_id}{extension}"
    target_dir = settings.UPLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    full_path = (target_dir / safe_filename).resolve()

    # Ensure path traversal cannot escape target_dir
    if not str(full_path).startswith(str(target_dir.resolve())):
        raise FileValidationError("Invalid storage path generated.")

    return unique_id, full_path
