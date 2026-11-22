"""
OpenCV Image Preprocessing Service
Khmer Government Document Intelligence System

Specialized image processing pipeline for Cambodian administrative documents:
- Automatic Deskew and Rotation Correction.
- CLAHE (Contrast Limited Adaptive Histogram Equalization) for faded government stamps and ink.
- Bilateral noise filtration preserving delicate Khmer script ligatures and subscripts.
- Adaptive and Otsu Binarization for high-precision OCR text separation.
- Support for JPG, PNG, and PDF page rasterization.
"""

import io
import math
import numpy as np
import cv2
from PIL import Image, ImageSequence
from typing import Tuple, List, Optional


class ImageProcessingError(Exception):
    """Raised when an error occurs during image processing or transformation."""
    pass


def load_image_bytes_to_cv2(image_bytes: bytes) -> np.ndarray:
    """Decodes raw image bytes into an OpenCV BGR numpy array."""
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ImageProcessingError("Failed to decode image with OpenCV.")
    return img


def convert_pdf_to_images(pdf_bytes: bytes, max_pages: int = 5) -> List[np.ndarray]:
    """
    Rasters PDF pages into OpenCV image arrays using Pillow.
    Falls back to single-page rendering or raises ImageProcessingError if unreadable.
    """
    try:
        pages = []
        with Image.open(io.BytesIO(pdf_bytes)) as pil_pdf:
            for i, page in enumerate(ImageSequence.Iterator(pil_pdf)):
                if i >= max_pages:
                    break
                # Convert to RGB mode
                rgb_page = page.convert("RGB")
                np_page = np.array(rgb_page)
                # Convert RGB to BGR for OpenCV
                bgr_page = cv2.cvtColor(np_page, cv2.COLOR_RGB2BGR)
                pages.append(bgr_page)
        if not pages:
            raise ImageProcessingError("No readable pages found in PDF document.")
        return pages
    except Exception as exc:
        raise ImageProcessingError(f"PDF rasterization failed: {str(exc)}")


def deskew_document(image: np.ndarray, max_skew_angle: float = 45.0) -> Tuple[np.ndarray, float]:
    """
    Detects and corrects document skew using contour orientation and minAreaRect.
    Works reliably on scanned administrative forms, birth certificates, and letters.
    """
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
        
        # Invert colors so text is white on black background
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

        # Find all foreground contours
        coords = np.column_stack(np.where(thresh > 0))
        if coords.shape[0] < 50:
            # Not enough text pixels to compute skew
            return image, 0.0

        angle = cv2.minAreaRect(coords)[-1]

        # Adjust OpenCV's angle to normal coordinate system
        if angle < -45:
            angle = -(90 + angle)
        elif angle > 45:
            angle = 90 - angle
        else:
            angle = -angle

        # If angle is negligible or extreme (false detection on borders), skip
        if abs(angle) < 0.5 or abs(angle) > max_skew_angle:
            return image, 0.0

        # Rotate the image around the center
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image,
            rotation_matrix,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        return rotated, angle
    except Exception:
        # If deskew computation fails on irregular layout, return original image safely
        return image, 0.0


def enhance_contrast_clahe(gray: np.ndarray) -> np.ndarray:
    """
    Applies Contrast Limited Adaptive Histogram Equalization (CLAHE).
    Significantly enhances faint Cambodian ink, seals, and carbon copy text.
    """
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def preprocess_for_ocr(
    image_bytes: bytes,
    apply_deskew: bool = True,
    apply_clahe: bool = True,
    use_adaptive_thresh: bool = False
) -> np.ndarray:
    """
    Comprehensive preprocessing pipeline tailored for Cambodian government documents:
    1. Decode to OpenCV BGR array.
    2. Optional Deskew / Rotation correction.
    3. Grayscale transformation.
    4. CLAHE contrast enhancement for faded or photocopied forms.
    5. Bilateral filtering to preserve fine Khmer ligatures and diacritics.
    6. Otsu or Adaptive Binarization.

    Returns:
        np.ndarray: Binarized single-channel 8-bit image ready for Tesseract OCR.
    """
    # 1. Decode
    image = load_image_bytes_to_cv2(image_bytes)

    # 2. Deskew
    if apply_deskew:
        image, _ = deskew_document(image)

    # 3. Grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # 4. Enhance contrast for faded official stamps & ink
    if apply_clahe:
        enhanced = enhance_contrast_clahe(gray)
    else:
        enhanced = gray

    # 5. Bilateral filtering: removes scanner noise without smearing delicate Khmer accents
    filtered = cv2.bilateralFilter(enhanced, d=7, sigmaColor=50, sigmaSpace=50)

    # 6. Binarization
    if use_adaptive_thresh:
        # Useful for uneven phone camera shadows
        binary = cv2.adaptiveThreshold(
            filtered,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=19,
            C=9
        )
    else:
        # Standard Otsu optimal thresholding
        _, binary = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return binary
