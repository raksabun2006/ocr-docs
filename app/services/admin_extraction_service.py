"""
Government Administrative Document Entity Extraction Service
Khmer Government Document Intelligence System

Extracts structured administrative entities from OCR text:
- Ministry, Department, and Sub-units
- Document Registration Number
- Location and Date of Issuance (Khmer Buddhist/Gregorian dates)
- Document Title / Declaration Type
- Sender & Recipient (សូមគោរពជូន, ផ្ញើជូន)
- Subject (កម្មវត្ថុ)
- Legal References (យោង)
- Main Content paragraphs
- Signatures, Titles, and Stamps
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from app.schemas.entities import GovernmentEntityData, SignerInfo


KHMER_DIGITS_MAP = {
    "០": "0", "១": "1", "២": "2", "៣": "3", "៤": "4",
    "៥": "5", "៦": "6", "៧": "7", "៨": "8", "៩": "9"
}


def normalize_khmer_numbers(text: str) -> str:
    """Converts Khmer numeral characters into Arabic numerals."""
    if not text:
        return ""
    res = []
    for char in text:
        res.append(KHMER_DIGITS_MAP.get(char, char))
    return "".join(res)


class AdminDocumentExtractor:
    """Extracts administrative metadata and fields from Cambodian official documents."""

    def extract(self, text: str, structured_ocr_data: Optional[Dict[str, Any]] = None) -> GovernmentEntityData:
        if not text:
            return GovernmentEntityData()

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        ministry = self._extract_ministry(lines)
        department = self._extract_department(lines)
        doc_num = self._extract_document_number(text)
        location, doc_date = self._extract_date_and_location(text)
        doc_title = self._extract_title(lines)
        recipient = self._extract_recipient(text)
        sender = self._extract_sender(lines)
        subject = self._extract_subject(text)
        references = self._extract_references(text)
        signers = self._extract_signers(lines)
        main_content = self._extract_main_content(lines, subject)

        return GovernmentEntityData(
            ministry=ministry,
            department=department,
            document_number=doc_num,
            location=location,
            document_date=doc_date,
            document_title=doc_title,
            recipient=recipient,
            sender=sender,
            subject=subject,
            references=references,
            main_content=main_content,
            signers=signers,
            tables_detected=0,
            metadata={
                "extracted_lines_count": len(lines),
                "has_royal_motto": any("ព្រះរាជាណាចក្រកម្ពុជា" in line for line in lines[:8]),
            }
        )

    def _extract_ministry(self, lines: List[str]) -> Optional[str]:
        """Detects Ministry or Governor authority (usually in top 10 lines)."""
        keywords = ["ក្រសួង", "រដ្ឋបាលរាជធានី", "រដ្ឋបាលខេត្ត", "រដ្ឋលេខាធិការដ្ឋាន", "ទីស្ដីការគណៈរដ្ឋមន្ត្រី", "ទីស្តីការគណៈរដ្ឋមន្ត្រី", "សាលារាជធានី", "សាលាខេត្ត"]
        for line in lines[:12]:
            for kw in keywords:
                if kw in line and not line.startswith("បានឃើញ"):
                    return line
        return None

    def _extract_department(self, lines: List[str]) -> Optional[str]:
        """Detects Department, General Directorate, or Office (below ministry)."""
        keywords = ["អគ្គនាយកដ្ឋាន", "នាយកដ្ឋាន", "មន្ទីរ", "ការិយាល័យ", "លេខាធិការដ្ឋាន", "រដ្ឋបាលស្រុក", "រដ្ឋបាលក្រុង", "រដ្ឋបាលខណ្ឌ"]
        for line in lines[:15]:
            for kw in keywords:
                if kw in line:
                    return line
        return None

    def _extract_document_number(self, text: str) -> Optional[str]:
        """Extracts registration number like: លេខ : ១២៣/២៤ ឬ លេខ..."""
        match = re.search(r"(?:លេខ|លិខិតលេខ|លេខចុះបញ្ជី)\s*[:\-–—\.]?\s*([០-៩0-9\sA-Za-z\/\.\-]+(?:\s*[\u1780-\u17D3]+)?)", text)
        if match:
            raw_val = match.group(1).strip()
            # Clean trailing punctuation
            raw_val = re.sub(r"[\.\,\;\:\s]+$", "", raw_val)
            if len(raw_val) >= 2:
                return raw_val
        return None

    def _extract_date_and_location(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts location and date:
        e.g. 'រាជធានីភ្នំពេញ ថ្ងៃទី... ខែ... ឆ្នាំ... ព.ស. ...'
        """
        location = None
        date_str = None

        # 1. Location match
        loc_match = re.search(r"(រាជធានីភ្នំពេញ|ភ្នំពេញ|ខេត្ត[\u1780-\u17D2]+|ក្រុង[\u1780-\u17D2]+)", text)
        if loc_match:
            location = loc_match.group(1).strip()

        # 2. Complete date match
        date_match = re.search(
            r"((?:ថ្ងៃ[\u1780-\u17D3\s]+)?\s*ថ្ងៃទី\s*[០-៩0-9]+\s*ខែ\s*[\u1780-\u17D2]+\s*ឆ្នាំ\s*[០-៩0-9]+(?:\s*ព\.?ស\.?\s*[០-៩0-9]+)?)",
            text
        )
        if date_match:
            date_str = date_match.group(1).strip()
        else:
            # Fallback simple date search
            simple_match = re.search(r"ថ្ងៃទី\s*([០-៩0-9\/\.\-]+)", text)
            if simple_match:
                date_str = simple_match.group(0).strip()

        return location, date_str

    def _extract_title(self, lines: List[str]) -> Optional[str]:
        """Detects document title in top 20 lines."""
        title_triggers = [
            "សេចក្តីជូនដំណឹង", "សេចក្ដីជូនដំណឹង", "សេចក្តីសម្រេច", "សេចក្ដីសម្រេច",
            "លិខិតអញ្ជើញ", "លិខិតស្នើសុំ", "ពាក្យស្នើសុំ", "របាយការណ៍", "លិខិតបញ្ជាក់",
            "លិខិតបង្គាប់ការ", "លិខិតឧទ្ទេសនាម", "សេចក្តីប្រកាស"
        ]
        for line in lines[:20]:
            clean = line.strip()
            for trig in title_triggers:
                if trig in clean:
                    return clean
        return None

    def _extract_recipient(self, text: str) -> Optional[str]:
        """Extracts recipient line (សូមគោរពជូន, ផ្ញើជូន, គោរពជូន) starting at line boundary."""
        match = re.search(r"(?:^|\n)\s*(?:សូមគោរពជូន|គោរពជូន|ផ្ញើជូន)\s*[:\-–—\.]?\s*([^\n\r]+)", text)
        if match:
            return match.group(1).strip()
        return None

    def _extract_sender(self, lines: List[str]) -> Optional[str]:
        """Extracts sender from header or signature lines."""
        for line in lines[:8]:
            if any(term in line for term in ["ក្រសួង", "រដ្ឋបាលរាជធានី", "រដ្ឋបាលខេត្ត", "គណៈកម្មាធិការ"]):
                return line
        return None

    def _extract_subject(self, text: str) -> Optional[str]:
        """Extracts subject: កម្មវត្ថុ : ..."""
        match = re.search(r"(?:កម្មវត្ថុ|កម្មវត្តុ)\s*[:\-–—\.]?\s*([^\n\r]+(?:\n[ \t]{2,}[^\n\r]+)?)", text)
        if match:
            return match.group(1).strip()
        return None

    def _extract_references(self, text: str) -> List[str]:
        """Extracts references: យោង : ..."""
        refs = []
        match = re.search(r"យោង\s*[:\-–—\.]?\s*([^\n\r]+(?:\n\s*[-–•*]\s*[^\n\r]+)*)", text)
        if match:
            block = match.group(1).strip()
            sublines = block.splitlines()
            for sl in sublines:
                cleaned = re.sub(r"^[-–•*\s\d\.]+", "", sl).strip()
                if cleaned:
                    refs.append(cleaned)
        return refs

    def _extract_signers(self, lines: List[str]) -> List[SignerInfo]:
        """Extracts signing authority and name from the bottom 15 lines."""
        signers: List[SignerInfo] = []
        roles_keywords = ["រដ្ឋមន្ត្រី", "រដ្ឋលេខាធិការ", "អភិបាល", "អគ្គនាយក", "ប្រធាននាយកដ្ឋាន", "ប្រធានមន្ទីរ", "ប្រធានការិយាល័យ", "មេឃុំ", "ចៅសង្កាត់"]

        # Examine bottom lines
        bottom_lines = lines[-12:] if len(lines) >= 12 else lines
        found_role = None
        for i, line in enumerate(bottom_lines):
            for role in roles_keywords:
                if role in line and not line.startswith("បានឃើញ"):
                    found_role = line.strip()
                    # Check next non-empty lines for the name
                    signer_name = None
                    for candidate in bottom_lines[i+1:]:
                        if candidate and not any(r in candidate for r in ["កាលបរិច្ឆេទ", "ទូរស័ព្ទ", "អ៊ីមែល", "Email"]):
                            signer_name = candidate.strip()
                            break
                    signers.append(SignerInfo(name=signer_name, role_title=found_role))
                    break
        return signers

    def _extract_main_content(self, lines: List[str], subject: Optional[str]) -> Optional[str]:
        """Captures the substantive paragraphs between subject/reference and signature block."""
        start_idx = 0
        end_idx = len(lines)

        # Find start after subject or references
        for i, line in enumerate(lines):
            if "កម្មវត្ថុ" in line or "យោង" in line:
                start_idx = max(start_idx, i + 1)

        # Skip references lines if present
        while start_idx < len(lines) and (lines[start_idx].startswith("-") or lines[start_idx].startswith("•")):
            start_idx += 1

        # Find end before signature block
        for i in range(len(lines) - 1, -1, -1):
            if any(term in lines[i] for term in ["ហត្ថលេខា", "រដ្ឋមន្ត្រី", "អភិបាល", "ប្រធាន", "ចៅសង្កាត់"]):
                end_idx = min(end_idx, i)
                break

        if start_idx < end_idx:
            content_lines = lines[start_idx:end_idx]
            return "\n\n".join(content_lines).strip()
        return None


admin_extractor = AdminDocumentExtractor()
