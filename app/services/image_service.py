"""
OpenCV Image Preprocessing Service (Khmer OCR Specialized)
Khmer Government Document Intelligence System

Advanced computer vision pipeline engineered specifically for Khmer script:
- Illumination Compensation & Shadow Removal (crucial for phone photos & desktop scans).
- Scale Normalization for small fonts and fine Khmer subscripts (ជើងអក្សរ).
- Graph Paper & Ruled Line Suppression (removes notebook grid lines and table grids).
- Automatic Deskew and Rotation Correction.
- CLAHE (Contrast Limited Adaptive Histogram Equalization) for faded inks and official seals.
- Adaptive Local Thresholding (Sauvola / Local Gaussian) & Enhanced Grayscale generation.
"""

import io
import math
import numpy as np
import cv2
from PIL import Image, ImageSequence
from typing import Tuple, List, Optional, Dict, Any


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
                rgb_page = page.convert("RGB")
                np_page = np.array(rgb_page)
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
        
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

        coords = np.column_stack(np.where(thresh > 0))
        if coords.shape[0] < 50:
            return image, 0.0

        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = -(90 + angle)
        elif angle > 45:
            angle = 90 - angle
        else:
            angle = -angle

        if abs(angle) < 0.5 or abs(angle) > max_skew_angle:
            return image, 0.0

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
        return image, 0.0


def normalize_scale_for_khmer(image: np.ndarray, min_dimension: int = 1800) -> Tuple[np.ndarray, float]:
    """
    Upscales documents if dimensions are too small for fine Khmer character recognition.
    Tesseract LSTM engine requires minimum 30px height for Khmer base + subscript glyphs.
    """
    h, w = image.shape[:2]
    max_dim = max(h, w)
    if max_dim < min_dimension:
        scale = min(2.5, float(min_dimension) / float(max_dim))
        scaled = cv2.resize(image, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        return scaled, scale
    return image, 1.0


def remove_shadows_and_normalize(gray: np.ndarray) -> np.ndarray:
    """
    Removes mobile phone shadows and uneven desk lighting:
    Estimates the background illumination plane using morphological dilation,
    subtracts it, and stretches the histogram to full dynamic range.
    """
    # Morphological dilation with large kernel to approximate paper background
    kernel_size = 21
    dilated = cv2.dilate(gray, np.ones((kernel_size, kernel_size), np.uint8))
    bg_approx = cv2.medianBlur(dilated, 25)
    
    # Difference from background
    diff = 255 - cv2.absdiff(gray, bg_approx)
    
    # Normalize to [0, 255]
    norm = cv2.normalize(diff, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    return norm


def enhance_contrast_clahe(gray: np.ndarray, clip_limit: float = 3.0) -> np.ndarray:
    """
    Applies Contrast Limited Adaptive Histogram Equalization (CLAHE).
    Significantly enhances faint Cambodian ink, seals, and carbon copy text.
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    return clahe.apply(gray)


def suppress_graph_and_ruled_lines(bin_inv: np.ndarray, scale: float = 1.0) -> np.ndarray:
    """
    Detects and eliminates horizontal/vertical grid lines (from graph paper or notebooks)
    so Tesseract does not misidentify them as punctuation or tabular barriers.
    """
    line_len = max(25, int(30 * scale))
    h_k = cv2.getStructuringElement(cv2.MORPH_RECT, (line_len, 1))
    v_k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, line_len))

    h_lines = cv2.morphologyEx(bin_inv, cv2.MORPH_OPEN, h_k)
    v_lines = cv2.morphologyEx(bin_inv, cv2.MORPH_OPEN, v_k)
    grid_lines = cv2.add(h_lines, v_lines)

    # Subtract grid lines from text mask
    text_clean = cv2.subtract(bin_inv, grid_lines)

    # Reconnect tiny gaps in character strokes where the line intersected
    reconnected = cv2.morphologyEx(
        text_clean,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    )
    return reconnected


def generate_multi_representation_variants(image_bytes: bytes) -> Dict[str, np.ndarray]:
    """
    Builds multiple complementary image representations for adaptive multi-pass OCR:
    1. 'enhanced_gray': Normalized, shadow-free grayscale (best for Tesseract 5 LSTM neural net).
    2. 'clean_adaptive': High-contrast adaptive binarization with grid line suppression.
    3. 'standard_otsu': Classic Otsu binarization for clean printed official forms.
    """
    raw_img = load_image_bytes_to_cv2(image_bytes)

    # 1. Deskew
    deskewed, _ = deskew_document(raw_img)

    # 2. Scale normalization
    scaled, scale_factor = normalize_scale_for_khmer(deskewed, min_dimension=1800)

    # 3. Grayscale
    if len(scaled.shape) == 3:
        gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
    else:
        gray = scaled.copy()

    # 4. Shadow removal and illumination compensation
    shadow_free = remove_shadows_and_normalize(gray)

    # 5. CLAHE contrast enhancement
    enhanced_gray = enhance_contrast_clahe(shadow_free, clip_limit=2.5)

    # 6. Adaptive binarization
    bin_adaptive = cv2.adaptiveThreshold(
        enhanced_gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=25,
        C=11
    )

    # 7. Grid line suppression
    inv_adaptive = cv2.bitwise_not(bin_adaptive)
    clean_inv = suppress_graph_and_ruled_lines(inv_adaptive, scale=scale_factor)
    clean_adaptive = cv2.bitwise_not(clean_inv)

    # 8. Standard Otsu (fallback for high-contrast crisp laser prints)
    filtered = cv2.bilateralFilter(enhanced_gray, d=7, sigmaColor=50, sigmaSpace=50)
    _, standard_otsu = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return {
        "enhanced_gray": enhanced_gray,
        "clean_adaptive": clean_adaptive,
        "standard_otsu": standard_otsu,
        "scale_factor": scale_factor
    }


def preprocess_for_ocr(
    image_bytes: bytes,
    apply_deskew: bool = True,
    apply_clahe: bool = True,
    use_adaptive_thresh: bool = False
) -> np.ndarray:
    """
    Default unified preprocessing method.
    Returns the optimal binarized image for OCR.
    """
    variants = generate_multi_representation_variants(image_bytes)
    if use_adaptive_thresh:
        return variants["clean_adaptive"]
    return variants["standard_otsu"]
