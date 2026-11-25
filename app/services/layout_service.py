"""
Document Layout Analysis Service
Khmer Government Document Intelligence System

Analyzes scanned images and OCR tokens to detect document structure:
- Royal Motto (centered/right-aligned top header)
- Ministry & Department letterheads (top-left)
- Document numbers and registration IDs
- Location and Date of issuance (top-right)
- Titles and Subtitles (centered, bold)
- Recipient and Subject lines
- Body paragraphs with alignment and indentation
- Tables and List structures
- Signature and stamp blocks (bottom-right / bottom-left)
- Footers and page numbers
"""

import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from app.schemas.layout import LayoutElement, ElementTypeEnum, BoundingBox


class DocumentLayoutAnalyzer:
    """Analyzes text and structural layout of Khmer official documents."""

    def analyze(
        self,
        text: str,
        structured_ocr_data: Optional[Dict[str, Any]] = None,
        image_width: int = 1200,
        image_height: int = 1600
    ) -> List[LayoutElement]:
        """
        Parses OCR text and geometric data into semantic layout elements.
        """
        if not text or not text.strip():
            return []

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        elements: List[LayoutElement] = []
        total_lines = len(lines)

        in_table = False
        current_table_rows: List[List[str]] = []

        for idx, line in enumerate(lines):
            # Check for Table rows (lines with '|' or multiple tab/spaced tabular items)
            if "|" in line or (re.search(r"\S+\s{4,}\S+", line) and ("ល.រ" in line or "ចំនួន" in line or "តម្លៃ" in line or "ឈ្មោះ" in line)):
                cells = [c.strip() for c in line.split("|") if c.strip()] if "|" in line else [c.strip() for c in re.split(r"\s{4,}", line) if c.strip()]
                if len(cells) >= 2:
                    in_table = True
                    current_table_rows.append(cells)
                    continue

            # If we were accumulating a table and hit a non-table line, flush table
            if in_table and current_table_rows:
                elements.append(self._build_table_element(current_table_rows, idx, image_width, image_height, total_lines))
                current_table_rows = []
                in_table = False

            # Classify line into semantic layout element
            elem = self._classify_line_element(line, idx, total_lines, image_width, image_height)
            elements.append(elem)

        # Flush any trailing table
        if in_table and current_table_rows:
            elements.append(self._build_table_element(current_table_rows, total_lines, image_width, image_height, total_lines))

        return elements

    def _classify_line_element(
        self,
        line: str,
        line_idx: int,
        total_lines: int,
        img_w: int,
        img_h: int
    ) -> LayoutElement:
        """Classifies a line into semantic Khmer administrative element."""
        elem_id = f"elem_{uuid.uuid4().hex[:8]}"
        pos_ratio = line_idx / max(total_lines, 1)

        # 1. Royal Motto (usually top 15% of document)
        if pos_ratio <= 0.20 and any(kw in line for kw in ["ព្រះរាជាណាចក្រកម្ពុជា", "ជាតិ សាសនា ព្រះមហាក្សត្រ", "ជាតិសាសនាព្រះមហាក្សត្រ"]):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.ROYAL_MOTTO,
                text=line,
                alignment="center",
                font_weight="bold",
                is_heading=True,
                confidence=95.0,
                bounding_box=BoundingBox(x=int(img_w * 0.25), y=int(img_h * 0.05 + line_idx * 30), width=int(img_w * 0.5), height=35),
                metadata={"section": "royal_motto"}
            )

        # 2. Ministry / Organization Header (usually top 25% of document, left side)
        if pos_ratio <= 0.25 and any(kw in line for kw in ["ក្រសួង", "រដ្ឋបាលរាជធានី", "រដ្ឋបាលខេត្ត", "រដ្ឋលេខាធិការដ្ឋាន", "អគ្គនាយកដ្ឋាន", "មន្ទីរ"]):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.MINISTRY_HEADER,
                text=line,
                alignment="left",
                font_weight="bold",
                confidence=92.0,
                bounding_box=BoundingBox(x=int(img_w * 0.05), y=int(img_h * 0.05 + line_idx * 28), width=int(img_w * 0.4), height=30),
                metadata={"section": "letterhead"}
            )

        # 3. Document Number (left side under ministry header)
        if pos_ratio <= 0.30 and re.search(r"^(?:លេខ|លិខិតលេខ|លេខចុះបញ្ជី)\s*[:\-–—\.]", line):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.DOCUMENT_NUMBER,
                text=line,
                alignment="left",
                font_weight="normal",
                confidence=90.0,
                bounding_box=BoundingBox(x=int(img_w * 0.05), y=int(img_h * 0.12 + line_idx * 25), width=int(img_w * 0.35), height=25),
                metadata={"section": "reference_number"}
            )

        # 4. Date and Location (top right, under royal motto)
        if pos_ratio <= 0.35 and (re.search(r"(?:រាជធានីភ្នំពេញ|ភ្នំពេញ|ខេត្ត[\u1780-\u17D2]+)\s*,\s*ថ្ងៃទី", line) or "ថ្ងៃទី" in line and "ខែ" in line and "ឆ្នាំ" in line):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.DATE_LOCATION,
                text=line,
                alignment="right",
                font_weight="normal",
                confidence=90.0,
                bounding_box=BoundingBox(x=int(img_w * 0.5), y=int(img_h * 0.12 + line_idx * 25), width=int(img_w * 0.45), height=25),
                metadata={"section": "date_location"}
            )

        # 5. Document Title (centered, prominent in top 40%)
        title_triggers = [
            "សេចក្តីជូនដំណឹង", "សេចក្ដីជូនដំណឹង", "សេចក្តីសម្រេច", "សេចក្ដីសម្រេច",
            "លិខិតអញ្ជើញ", "លិខិតស្នើសុំ", "ពាក្យស្នើសុំ", "របាយការណ៍", "លិខិតបញ្ជាក់",
            "លិខិតបង្គាប់ការ", "លិខិតឧទ្ទេសនាម", "សេចក្តីប្រកាស", "សំបុត្រកំណើត"
        ]
        if pos_ratio <= 0.40 and any(trig in line for trig in title_triggers):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.DOCUMENT_TITLE,
                text=line,
                alignment="center",
                font_weight="bold",
                is_heading=True,
                confidence=96.0,
                bounding_box=BoundingBox(x=int(img_w * 0.2), y=int(img_h * 0.20 + line_idx * 30), width=int(img_w * 0.6), height=40),
                metadata={"section": "document_title"}
            )

        # 6. Recipient / Addressee
        if re.search(r"^(?:សូមគោរពជូន|គោរពជូន|ផ្ញើជូន|ជូន)\s*[:\-–—\.]?", line):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.RECIPIENT,
                text=line,
                alignment="left",
                font_weight="bold",
                confidence=91.0,
                bounding_box=BoundingBox(x=int(img_w * 0.08), y=int(img_h * 0.25 + line_idx * 25), width=int(img_w * 0.8), height=28),
                metadata={"section": "recipient"}
            )

        # 7. Subject (កម្មវត្ថុ)
        if re.search(r"^(?:កម្មវត្ថុ|កម្មវត្តុ)\s*[:\-–—\.]?", line):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.SUBJECT,
                text=line,
                alignment="left",
                font_weight="bold",
                confidence=93.0,
                bounding_box=BoundingBox(x=int(img_w * 0.08), y=int(img_h * 0.28 + line_idx * 25), width=int(img_w * 0.85), height=28),
                metadata={"section": "subject"}
            )

        # 8. Reference (យោង)
        if re.search(r"^យោង\s*[:\-–—\.]?", line):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.REFERENCE,
                text=line,
                alignment="left",
                font_weight="normal",
                confidence=91.0,
                bounding_box=BoundingBox(x=int(img_w * 0.08), y=int(img_h * 0.32 + line_idx * 25), width=int(img_w * 0.85), height=26),
                metadata={"section": "reference"}
            )

        # 9. List Items (bullets or numbered items)
        if re.search(r"^[-–•*]\s+", line) or re.search(r"^(?:[០-៩0-9]+|[ក-អa-zA-Z])\s*[\.\)]\s+", line):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.LIST_ITEM,
                text=line,
                alignment="left",
                font_weight="normal",
                confidence=88.0,
                bounding_box=BoundingBox(x=int(img_w * 0.12), y=int(img_h * 0.35 + line_idx * 24), width=int(img_w * 0.8), height=24),
                metadata={"section": "list_item"}
            )

        # 10. Signature and Stamp Block (bottom 25% of document)
        if pos_ratio >= 0.70 and any(kw in line for kw in ["រដ្ឋមន្ត្រី", "រដ្ឋលេខាធិការ", "អភិបាល", "អគ្គនាយក", "ប្រធាន", "មេឃុំ", "ចៅសង្កាត់", "ហត្ថលេខា", "ត្រា"]):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.SIGNATURE_BLOCK,
                text=line,
                alignment="right",
                font_weight="bold",
                confidence=92.0,
                bounding_box=BoundingBox(x=int(img_w * 0.55), y=int(img_h * 0.80 + (line_idx - int(total_lines * 0.8)) * 26), width=int(img_w * 0.4), height=35),
                metadata={"section": "signature_block"}
            )

        # 11. Footer / Contact / Page numbers (bottom-most lines)
        if pos_ratio >= 0.92 and (any(kw in line for kw in ["ទូរស័ព្ទ", "ទូរសារ", "Email", "អ៊ីមែល", "អាសយដ្ឋាន", "ផ្លូវជាតិ", "សង្កាត់"]) or re.match(r"^[-–—\s\d\/]+$", line)):
            return LayoutElement(
                id=elem_id,
                element_type=ElementTypeEnum.FOOTER,
                text=line,
                alignment="center",
                font_weight="normal",
                confidence=85.0,
                bounding_box=BoundingBox(x=int(img_w * 0.1), y=int(img_h * 0.95), width=int(img_w * 0.8), height=20),
                metadata={"section": "footer"}
            )

        # 12. Default: Standard Body Paragraph
        return LayoutElement(
            id=elem_id,
            element_type=ElementTypeEnum.PARAGRAPH,
            text=line,
            alignment="justify",
            font_weight="normal",
            confidence=85.0,
            bounding_box=BoundingBox(x=int(img_w * 0.08), y=int(img_h * 0.35 + line_idx * 24), width=int(img_w * 0.84), height=24),
            metadata={"section": "body_paragraph"}
        )

    def _build_table_element(
        self,
        table_rows: List[List[str]],
        end_idx: int,
        img_w: int,
        img_h: int,
        total_lines: int
    ) -> LayoutElement:
        """Constructs a TABLE layout element from parsed tabular rows."""
        return LayoutElement(
            id=f"elem_{uuid.uuid4().hex[:8]}",
            element_type=ElementTypeEnum.TABLE,
            text="\n".join(["\t".join(row) for row in table_rows]),
            alignment="center",
            font_weight="normal",
            confidence=90.0,
            table_data=table_rows,
            bounding_box=BoundingBox(
                x=int(img_w * 0.06),
                y=int(img_h * (end_idx / max(total_lines, 1))),
                width=int(img_w * 0.88),
                height=len(table_rows) * 28
            ),
            metadata={"row_count": len(table_rows), "col_count": max(len(r) for r in table_rows)}
        )


layout_analyzer = DocumentLayoutAnalyzer()
