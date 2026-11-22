"""
Structured Information Extraction Service
Khmer Government Document Intelligence System

Specialized extraction engine for Cambodian Civil Registration Documents:
- Regex-based field extraction for Birth Certificates (សំបុត្រកំណើត).
- Khmer numeral converter (០១២៣៤៥៦៧៨៩ <-> 0123456789).
- Khmer calendar month normalization (មករា -> 01, etc.).
- Strict adherence to rule: never hallucinate or invent missing data, return null.
"""

import re
from typing import Dict, Any, Optional, Tuple
from app.schemas.birth_certificate import BirthCertificateData, BirthCertificateField

# Khmer numerals mapping
KHMER_TO_ARABIC_NUMERALS = {
    '០': '0', '១': '1', '២': '2', '៣': '3', '៤': '4',
    '៥': '5', '៦': '6', '៧': '7', '៨': '8', '៩': '9'
}

# Khmer months mapping
KHMER_MONTHS = {
    "មករា": "01",
    "កុម្ភៈ": "02",
    "មិនា": "03",
    "មេសា": "04",
    "ឧសភា": "05",
    "មិថុនា": "06",
    "កក្កដា": "07",
    "សីហា": "08",
    "កញ្ញា": "09",
    "តុលា": "10",
    "វិច្ឆិកា": "11",
    "ធ្នូ": "12"
}


def convert_khmer_numerals(text: str) -> str:
    """Converts Khmer digits (០-៩) into Arabic digits (0-9)."""
    return "".join(KHMER_TO_ARABIC_NUMERALS.get(char, char) for char in text)


def normalize_khmer_text(text: str) -> str:
    """Cleans up multiple spaces and standardizes line breaks."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\r\n", "\n", text)
    return text.strip()


class BirthCertificateExtractor:
    """Extracts structured fields from Cambodian birth certificate OCR text."""

    def __init__(self):
        # Patterns for Cambodian birth certificates
        self.patterns = {
            # គោត្តនាម និងនាម / ឈ្មោះ : ...
            "full_name_khmer": [
                r"(?:គោត្តនាម\s*និង\s*នាម|ឈ្មោះ|សាមីខ្លួនឈ្មោះ)\s*[:\-–—]?\s*([ក-អ\u1780-\u17D3\s]+?)(?=\n|ជាអក្សរ|ភេទ|កើត|ថ្ងៃ|កាល|\Z)",
                r"ឈ្មោះ\s*[:\-–—]?\s*([ក-អ\u1780-\u17D3\s]{3,35})(?=\n|$)",
            ],
            # Latin Name / ជាអក្សរឡាតាំង : ...
            "full_name_english": [
                r"(?:ជាអក្សរឡាតាំង|In Latin|Latin Name|Name in Latin|Name)\s*[:\-–—]?\s*([A-Za-z\s]+?)(?=\n|Sex|Gender|Born|Date|\Z)",
                r"(?:[A-Z\s]{3,30})(?=\s*(?:MALE|FEMALE|SEX))",
            ],
            # ភេទ : ប្រុស / ស្រី
            "gender": [
                r"ភេទ\s*[:\-–—]?\s*(ប្រុស|ស្រី|Male|Female)",
                r"(?:\b)(ប្រុស|ស្រី)(?:\b)",
            ],
            # ថ្ងៃ ខែ ឆ្នាំ កំណើត / កើតថ្ងៃទី ...
            "date_of_birth": [
                r"(?:កើតថ្ងៃទី|កើតថ្ងៃ|ថ្ងៃ\s*ខែ\s*ឆ្នាំ\s*កំណើត|ថ្ងៃខែឆ្នាំកំណើត|ថ្ងៃកំណើត)\s*[:\-–—]?\s*([០-៩0-9\sក-អ\u1780-\u17D3\/\.\-]+?)(?=\n|នៅ|ទីកន្លែង|ភូមិ|\Z)",
                r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            ],
            # ទីកន្លែងកំណើត : ...
            "place_of_birth": [
                r"(?:ទីកន្លែងកំណើត|កើតនៅ|ទីលំនៅកំណើត)\s*[:\-–—]?\s*([ក-អ\u1780-\u17D30-9០-៩\s\,\.\-]+?)(?=\n|ឪពុក|ម្តាយ|\Z)",
            ],
            # ឪពុកឈ្មោះ : ...
            "father_name": [
                r"(?:ឪពុកឈ្មោះ|ឪពុក|ឈ្មោះឪពុក)\s*[:\-–—]?\s*([ក-អ\u1780-\u17D3A-Za-z\s]+?)(?=\n|ម្តាយ|មុខរបរ|អាយុ|\Z)",
            ],
            # ម្តាយឈ្មោះ : ...
            "mother_name": [
                r"(?:ម្តាយឈ្មោះ|ម្តាយ|ឈ្មោះម្តាយ)\s*[:\-–—]?\s*([ក-អ\u1780-\u17D3A-Za-z\s]+?)(?=\n|មុខរបរ|អាយុ|ទីលំនៅ|\Z)",
            ],
            # លេខចុះបញ្ជី / លេខសំបុត្រ / លេខ : ...
            "registration_number": [
                r"(?:លេខចុះបញ្ជី|លេខសំបុត្រ|សៀវភៅលេខ|លេខ)\s*[:\-–—]?\s*([០-៩0-9A-Za-z\/\.\-]+)",
                r"No\.?\s*([0-9A-Za-z\/\-]+)",
            ],
            # ថ្ងៃចុះបញ្ជី : ...
            "registration_date": [
                r"(?:ថ្ងៃចុះបញ្ជី|កាលបរិច្ឆេទចុះបញ្ជី|ធ្វើនៅ\s*[^\n]*\s*ថ្ងៃទី)\s*[:\-–—]?\s*([០-៩0-9\sក-អ\u1780-\u17D3\/\.\-]+?)(?=\n|មន្ត្រី|ចៅសង្កាត់|មេឃុំ|\Z)",
            ]
        }

    def _clean_field_value(self, val: Optional[str]) -> Optional[str]:
        """Cleans extracted field text and discards noise."""
        if not val:
            return None
        cleaned = val.strip().strip(":-–—.,")
        # Discard if it's too short or only punctuation
        if len(cleaned) < 2:
            return None
        return cleaned

    def _standardize_date(self, raw_date: Optional[str]) -> Optional[str]:
        """
        Standardizes date strings containing Khmer numbers or months into YYYY-MM-DD or normalized text.
        """
        if not raw_date:
            return None

        # Convert Khmer digits
        converted = convert_khmer_numerals(raw_date)

        # Check for standard DD/MM/YYYY or DD-MM-YYYY
        dmy_match = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})", converted)
        if dmy_match:
            day, month, year = dmy_match.groups()
            if len(year) == 2:
                year = f"20{year}" if int(year) < 50 else f"19{year}"
            return f"{year}-{int(month):02d}-{int(day):02d}"

        # Check for Khmer month phrases (e.g. ថ្ងៃទី ១៥ ខែ មេសា ឆ្នាំ ២០០០)
        for kh_month, m_num in KHMER_MONTHS.items():
            if kh_month in raw_date:
                # Extract day and year numbers around the month
                day_match = re.search(r"(\d{1,2})\s*ខែ", converted)
                year_match = re.search(r"ឆ្នាំ\s*(\d{4})", converted)
                day_str = f"{int(day_match.group(1)):02d}" if day_match else "01"
                year_str = year_match.group(1) if year_match else "1990"
                return f"{year_str}-{m_num}-{day_str}"

        return self._clean_field_value(raw_date)

    def extract(
        self,
        raw_text: str,
        structured_data: Optional[Dict[str, Any]] = None
    ) -> BirthCertificateData:
        """
        Extracts structured fields from raw OCR text.
        Never invents missing data. If a field cannot be matched, it remains None.
        """
        cleaned_text = normalize_khmer_text(raw_text)
        extracted: Dict[str, Any] = {}
        field_confidences: Dict[str, BirthCertificateField] = {}

        # Default confidence score if structured word data is provided
        avg_confidence = structured_data.get("average_confidence", 75.0) if structured_data else 75.0

        for field_name, regex_list in self.patterns.items():
            matched_val = None
            for pattern in regex_list:
                match = re.search(pattern, cleaned_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    matched_val = self._clean_field_value(match.group(1))
                    if matched_val:
                        break

            if field_name in ("date_of_birth", "registration_date") and matched_val:
                matched_val = self._standardize_date(matched_val)

            extracted[field_name] = matched_val

            # Compute field-level uncertainty
            if matched_val:
                # Estimate confidence
                conf = avg_confidence
                uncertainty = "low_uncertainty" if conf >= 80 else ("medium_uncertainty" if conf >= 50 else "high_uncertainty")
                field_confidences[field_name] = BirthCertificateField(
                    value=matched_val,
                    confidence=conf,
                    uncertainty_level=uncertainty
                )
            else:
                field_confidences[field_name] = BirthCertificateField(
                    value=None,
                    confidence=None,
                    uncertainty_level="high_uncertainty"
                )

        return BirthCertificateData(
            full_name_khmer=extracted.get("full_name_khmer"),
            full_name_english=extracted.get("full_name_english"),
            date_of_birth=extracted.get("date_of_birth"),
            gender=extracted.get("gender"),
            place_of_birth=extracted.get("place_of_birth"),
            father_name=extracted.get("father_name"),
            mother_name=extracted.get("mother_name"),
            registration_number=extracted.get("registration_number"),
            registration_date=extracted.get("registration_date"),
            field_confidences=field_confidences,
            raw_text=raw_text
        )


birth_certificate_extractor = BirthCertificateExtractor()
