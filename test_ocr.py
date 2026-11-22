"""
Standalone OCR Verification Script
Khmer Government Document Intelligence System

Usage:
    python test_ocr.py
    python test_ocr.py --image path/to/document.jpg
"""

import os
import sys
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.services.ocr_service import ocr_service
from app.services.image_service import preprocess_for_ocr


def generate_sample_khmer_document(output_path: str = "sample_test_doc.png") -> str:
    """Generates a test document containing Khmer and English administrative text."""
    width, height = 750, 450
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    # Windows Khmer fonts
    font_candidates = [
        r"C:\Windows\Fonts\KhmerOSsys.ttf",
        r"C:\Windows\Fonts\KhmerUI.ttf",
        r"C:\Windows\Fonts\daunpenh.ttf",
        r"C:\Windows\Fonts\LeelawUI.ttf",
    ]
    font_path = None
    for cand in font_candidates:
        if os.path.exists(cand):
            font_path = cand
            break

    font_large = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()
    font_medium = ImageFont.truetype(font_path, 22) if font_path else ImageFont.load_default()

    draw.text((120, 25), "ព្រះរាជាណាចក្រកម្ពុជា", fill="black", font=font_large)
    draw.text((160, 65), "ជាតិ សាសនា ព្រះមហាក្សត្រ", fill="black", font=font_medium)
    draw.text((180, 115), "សេចក្តីចម្លងសំបុត្រកំណើត", fill="black", font=font_large)
    draw.text((220, 155), "BIRTH CERTIFICATE", fill="black", font=font_medium)
    draw.line([(40, 190), (710, 190)], fill="black", width=2)

    draw.text((50, 210), "គោត្តនាម និង នាម : សុខ សាន", fill="black", font=font_medium)
    draw.text((50, 250), "In Latin : SOK SAN", fill="black", font=font_medium)
    draw.text((50, 290), "ភេទ : ប្រុស (MALE)", fill="black", font=font_medium)
    draw.text((50, 330), "កើតថ្ងៃទី : ១៥ ខែ មេសា ឆ្នាំ ២០០០ (15-04-2000)", fill="black", font=font_medium)
    draw.text((50, 370), "លេខសំបុត្រ : 1234/2000", fill="black", font=font_medium)

    img.save(output_path)
    return output_path


def run_checks(image_path: str = None) -> bool:
    print("=" * 70)
    print(" KHMER GOVERNMENT DOCUMENT INTELLIGENCE SYSTEM - OCR VERIFICATION")
    print("=" * 70)

    # 1. Config Check
    print(f"\n[1] Checking Configuration:")
    print(f"    - Tesseract Binary:  {settings.TESSERACT_CMD}")
    print(f"    - Tessdata Dir:      {settings.get_clean_tessdata_dir()}")
    print(f"    - Default Languages: {settings.OCR_DEFAULT_LANGUAGES}")

    # 2. Executable & Language Verification
    print(f"\n[2] Verifying Tesseract OCR Engine & Language Packs:")
    env = ocr_service.verify_environment()
    print(f"    - Executable Found:  {'✓ YES' if env['tesseract_installed'] else '✗ NO'}")
    print(f"    - Available Models:  {', '.join(env['languages_found']) if env['languages_found'] else 'None'}")
    print(f"    - English (eng):     {'✓ YES' if env['has_english'] else '✗ MISSING'}")
    print(f"    - Khmer (khm):       {'✓ YES' if env['has_khmer'] else '✗ MISSING'}")

    if not env['tesseract_installed']:
        print("\n[ERROR] Tesseract executable not found at specified path!")
        return False

    if not (env['has_english'] and env['has_khmer']):
        print("\n[WARNING] English or Khmer language models missing in tessdata directory.")
        print(f"Directory checked: {settings.get_clean_tessdata_dir()}")

    # 3. OCR Test
    temp_generated = False
    if not image_path:
        print(f"\n[3] Generating Synthetic Khmer Government Document Sample...")
        image_path = generate_sample_khmer_document("test_verify_khmer_doc.png")
        temp_generated = True

    print(f"\n[4] Running OpenCV Preprocessing & Multi-Language OCR on: {image_path}")
    try:
        with open(image_path, "rb") as f:
            raw_bytes = f.read()

        preprocessed = preprocess_for_ocr(raw_bytes)
        print("    ✓ OpenCV Preprocessing completed (Deskew, CLAHE, Bilateral Filter, Otsu).")

        # Run OCR
        extracted_text = ocr_service.extract_text(preprocessed, languages="khm+eng")
        structured_data = ocr_service.extract_structured_ocr_data(preprocessed, languages="khm+eng")

        print("\n" + "-" * 70)
        print("EXTRACTED TEXT:")
        print("-" * 70)
        print(extracted_text)
        print("-" * 70)
        print(f"Average Confidence: {structured_data['average_confidence']}%")
        print(f"Total Words Detected: {structured_data['total_words']}")
        print("-" * 70)

        # Basic assertion
        if len(extracted_text) > 5:
            print("\n✓ SUCCESS: OCR pipeline verified successfully.")
            success = True
        else:
            print("\n✗ FAILURE: Extracted text was unexpectedly empty.")
            success = False

    except Exception as exc:
        print(f"\n[ERROR] OCR Test encountered an exception: {exc}")
        success = False
    finally:
        if temp_generated and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError:
                pass

    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Tesseract Khmer + English OCR")
    parser.add_argument("--image", type=str, default=None, help="Path to test image")
    args = parser.parse_args()

    passed = run_checks(args.image)
    sys.exit(0 if passed else 1)
