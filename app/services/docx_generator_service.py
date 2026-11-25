"""
Editable Microsoft Word (.docx) Generation Service
Khmer Government Document Intelligence System

Generates structured, fully editable Microsoft Word (.docx) documents with:
- Standard A4 page geometry & margins (2.54 cm).
- Khmer Unicode font styling (Khmer OS Muol Light for headings, Khmer OS Siemreap for body).
- OpenXML Complex Script (w:cs) font configuration for native Khmer rendering.
- Official Cambodian administrative two-column letterheads.
- Styled titles, subject, legal references, and justified body paragraphs.
- Editable Word tables with borders and formatting.
- Signature blocks and document footers.
- Preservation of human reviewer edits and corrections.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import docx
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

from app.schemas.layout import LayoutElement, ElementTypeEnum
from app.schemas.entities import GovernmentEntityData
from app.config import settings, BASE_DIR


# Official Standard Fonts
FONT_HEADING = "Khmer OS Muol Light"
FONT_TITLE = "Khmer OS Muol"
FONT_BODY = "Khmer OS Siemreap"
FONT_FALLBACK = "Battambang"


def set_run_khmer_font(
    run,
    font_name: str = FONT_BODY,
    size_pt: float = 12.0,
    bold: bool = False,
    italic: bool = False,
    color_rgb: Optional[RGBColor] = None
) -> None:
    """
    Sets font properties on a Word run, explicitly adding OpenXML complex script (w:cs)
    tags so Microsoft Word renders Khmer Unicode with proper shaping and ligatures.
    """
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    if color_rgb:
        run.font.color.rgb = color_rgb

    # OpenXML Complex Script configuration: <w:rFonts w:ascii="..." w:hAnsi="..." w:cs="..."/>
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)

    rFonts.set(qn("w:ascii"), font_name)
    rFonts.set(qn("w:hAnsi"), font_name)
    rFonts.set(qn("w:cs"), font_name)

    # Enable complex script flag
    if bold:
        bCs = rPr.find(qn("w:bCs"))
        if bCs is None:
            bCs = OxmlElement("w:bCs")
            rPr.append(bCs)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets internal padding on a table cell in twentieths of a point (dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for m, val in [("w:top", top), ("w:bottom", bottom), ("w:left", left), ("w:right", right)]:
        node = OxmlElement(m)
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def set_cell_shading(cell, color_hex: str):
    """Sets cell background fill color."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)


class DocxGeneratorService:
    """Generates production-grade editable Word documents from scanned Khmer government records."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or (BASE_DIR / "uploads" / "docx")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_docx(
        self,
        document_id: str,
        filename_prefix: str,
        elements: Optional[List[LayoutElement]] = None,
        entities: Optional[GovernmentEntityData] = None,
        corrected_text: Optional[str] = None
    ) -> Path:
        """
        Builds and saves an editable .docx file reflecting the document's structure and edits.
        """
        doc = docx.Document()

        # 1. Setup Page Geometry (A4, 2.54cm margins)
        section = doc.sections[0]
        section.page_width = Inches(8.27)       # 210 mm
        section.page_height = Inches(11.69)     # 297 mm
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(2.8)           # Official Cambodian margin: Left 2.8cm, Right 2.0cm
        section.right_margin = Cm(2.0)

        # 2. Render content based on available data
        if elements and len(elements) > 0:
            self._render_from_elements(doc, elements)
        elif corrected_text:
            self._render_from_text(doc, corrected_text)
        else:
            # Fallback simple template
            p = doc.add_paragraph()
            run = p.add_run("មិនមានទិន្នន័យអត្ថបទ")
            set_run_khmer_font(run, FONT_BODY, 12)

        # 3. Save Document to disk
        safe_prefix = "".join(c for c in filename_prefix if c.isalnum() or c in ("-", "_")).strip() or "document"
        output_path = self.output_dir / f"{safe_prefix}_{document_id[:8]}.docx"
        doc.save(str(output_path))
        return output_path

    def _render_from_elements(self, doc: docx.Document, elements: List[LayoutElement]) -> None:
        """Renders Word document faithfully following detected layout elements."""
        # Check if we have two-column letterhead elements (Motto on right, Ministry on left)
        motto_elem = next((e for e in elements if e.element_type == ElementTypeEnum.ROYAL_MOTTO), None)
        ministry_elem = next((e for e in elements if e.element_type == ElementTypeEnum.MINISTRY_HEADER), None)
        doc_num_elem = next((e for e in elements if e.element_type == ElementTypeEnum.DOCUMENT_NUMBER), None)
        date_elem = next((e for e in elements if e.element_type == ElementTypeEnum.DATE_LOCATION), None)

        rendered_ids = set()

        # If we have both letterhead components, construct official 2-column header table
        if motto_elem and (ministry_elem or doc_num_elem):
            self._render_official_header_table(doc, ministry_elem, doc_num_elem, motto_elem, date_elem)
            for e in [motto_elem, ministry_elem, doc_num_elem, date_elem]:
                if e:
                    rendered_ids.add(e.id)

        # Render remaining elements sequentially
        for elem in elements:
            if elem.id in rendered_ids:
                continue

            if elem.element_type == ElementTypeEnum.ROYAL_MOTTO:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.space_before = Pt(0)
                run = p.add_run(elem.text)
                set_run_khmer_font(run, FONT_HEADING, 13, bold=True)

            elif elem.element_type == ElementTypeEnum.MINISTRY_HEADER:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.space_before = Pt(0)
                run = p.add_run(elem.text)
                set_run_khmer_font(run, FONT_HEADING, 11, bold=True)

            elif elem.element_type == ElementTypeEnum.DOCUMENT_NUMBER:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_after = Pt(4)
                run = p.add_run(elem.text)
                set_run_khmer_font(run, FONT_BODY, 11, bold=False)

            elif elem.element_type == ElementTypeEnum.DATE_LOCATION:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p.paragraph_format.space_after = Pt(8)
                run = p.add_run(elem.text)
                set_run_khmer_font(run, FONT_BODY, 11, italic=False)

            elif elem.element_type == ElementTypeEnum.DOCUMENT_TITLE:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(14)
                p.paragraph_format.space_after = Pt(12)
                run = p.add_run(elem.text)
                set_run_khmer_font(run, FONT_TITLE, 14, bold=True)

            elif elem.element_type == ElementTypeEnum.RECIPIENT:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.space_before = Pt(6)
                run = p.add_run(elem.text)
                set_run_khmer_font(run, FONT_BODY, 12, bold=True)

            elif elem.element_type == ElementTypeEnum.SUBJECT:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.left_indent = Inches(0.2)
                # Split subject label from text if present
                if ":" in elem.text:
                    label, val = elem.text.split(":", 1)
                    r_lbl = p.add_run(label + " : ")
                    set_run_khmer_font(r_lbl, FONT_BODY, 11.5, bold=True)
                    r_val = p.add_run(val.strip())
                    set_run_khmer_font(r_val, FONT_BODY, 11.5, bold=False)
                else:
                    run = p.add_run(elem.text)
                    set_run_khmer_font(run, FONT_BODY, 11.5, bold=True)

            elif elem.element_type == ElementTypeEnum.REFERENCE:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.left_indent = Inches(0.2)
                if ":" in elem.text:
                    label, val = elem.text.split(":", 1)
                    r_lbl = p.add_run(label + " : ")
                    set_run_khmer_font(r_lbl, FONT_BODY, 11, bold=True)
                    r_val = p.add_run(val.strip())
                    set_run_khmer_font(r_val, FONT_BODY, 11, bold=False)
                else:
                    run = p.add_run(elem.text)
                    set_run_khmer_font(run, FONT_BODY, 11, bold=False)

            elif elem.element_type == ElementTypeEnum.TABLE and elem.table_data:
                self._render_table(doc, elem.table_data)

            elif elem.element_type == ElementTypeEnum.LIST_ITEM:
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.4)
                p.paragraph_format.space_after = Pt(3)
                run = p.add_run(elem.text)
                set_run_khmer_font(run, FONT_BODY, 11.5, bold=False)

            elif elem.element_type == ElementTypeEnum.SIGNATURE_BLOCK:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p.paragraph_format.space_before = Pt(18)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.right_indent = Inches(0.5)
                run = p.add_run(elem.text)
                set_run_khmer_font(run, FONT_HEADING, 12, bold=True)

            elif elem.element_type == ElementTypeEnum.FOOTER:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(12)
                run = p.add_run(elem.text)
                set_run_khmer_font(run, FONT_BODY, 9.5, italic=True)

            else:
                # Default Body Paragraph
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.paragraph_format.first_line_indent = Inches(0.4)  # Standard Cambodian first line indent
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.line_spacing = 1.15
                run = p.add_run(elem.text)
                set_run_khmer_font(run, FONT_BODY, 11.5, bold=False)

    def _render_official_header_table(
        self,
        doc: docx.Document,
        ministry: Optional[LayoutElement],
        doc_num: Optional[LayoutElement],
        motto: Optional[LayoutElement],
        date_elem: Optional[LayoutElement]
    ) -> None:
        """
        Renders the standard 2-column Cambodian government letterhead:
        Left Column: Ministry Name & Document Number
        Right Column: Royal Motto & Issuance Date
        """
        table = doc.add_table(rows=1, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        # Set column widths (Left 45%, Right 55%)
        table.columns[0].width = Inches(3.2)
        table.columns[1].width = Inches(3.8)

        left_cell = table.cell(0, 0)
        right_cell = table.cell(0, 1)

        # Clear borders on letterhead table
        self._remove_table_borders(table)

        # 1. Left cell: Ministry & Document Number
        p_left = left_cell.paragraphs[0]
        p_left.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_left.paragraph_format.space_after = Pt(2)
        if ministry:
            r_min = p_left.add_run(ministry.text)
            set_run_khmer_font(r_min, FONT_HEADING, 10.5, bold=True)

        if doc_num:
            p_num = left_cell.add_paragraph()
            p_num.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p_num.paragraph_format.space_after = Pt(4)
            r_num = p_num.add_run(doc_num.text)
            set_run_khmer_font(r_num, FONT_BODY, 10.5, bold=False)

        # 2. Right cell: Royal Motto & Date
        p_right = right_cell.paragraphs[0]
        p_right.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_right.paragraph_format.space_after = Pt(2)
        if motto:
            # Check if motto is two lines or one
            motto_lines = [line.strip() for line in motto.text.splitlines() if line.strip()]
            for ml in motto_lines:
                r_mot = p_right.add_run(ml + "\n")
                set_run_khmer_font(r_mot, FONT_HEADING, 11, bold=True)

        if date_elem:
            p_date = right_cell.add_paragraph()
            p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            p_date.paragraph_format.space_after = Pt(4)
            r_date = p_date.add_run(date_elem.text)
            set_run_khmer_font(r_date, FONT_BODY, 10, italic=False)

        # Spacer paragraph after header table
        p_space = doc.add_paragraph()
        p_space.paragraph_format.space_before = Pt(8)
        p_space.paragraph_format.space_after = Pt(4)

    def _render_table(self, doc: docx.Document, table_data: List[List[str]]) -> None:
        """Renders an editable table with borders, padding, and centered headers."""
        if not table_data or len(table_data) == 0:
            return

        rows_count = len(table_data)
        cols_count = max(len(r) for r in table_data)

        table = doc.add_table(rows=rows_count, cols=cols_count)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"  # Standard thin border grid

        for r_idx, row in enumerate(table_data):
            for c_idx in range(cols_count):
                cell = table.cell(r_idx, c_idx)
                cell_text = row[c_idx] if c_idx < len(row) else ""
                cell.text = ""  # clear default paragraph
                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(3)
                p.paragraph_format.space_after = Pt(3)

                is_header_row = (r_idx == 0)
                if is_header_row:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    set_cell_shading(cell, "F2F2F2")
                    run = p.add_run(cell_text)
                    set_run_khmer_font(run, FONT_BODY, 10.5, bold=True)
                else:
                    # Align numbers to center, text to left
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if cell_text.isdigit() or len(cell_text) <= 3 else WD_ALIGN_PARAGRAPH.LEFT
                    run = p.add_run(cell_text)
                    set_run_khmer_font(run, FONT_BODY, 10.5, bold=False)

                set_cell_margins(cell, top=100, bottom=100, left=150, right=150)

        # Spacing after table
        p_after = doc.add_paragraph()
        p_after.paragraph_format.space_after = Pt(6)

    def _render_from_text(self, doc: docx.Document, text: str) -> None:
        """Simple paragraph rendering from raw or edited text string."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for p_text in paragraphs:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.first_line_indent = Inches(0.4)
            p.paragraph_format.space_after = Pt(6)
            run = p.add_run(p_text)
            set_run_khmer_font(run, FONT_BODY, 11.5)

    def _remove_table_borders(self, table) -> None:
        """Clears visual borders from an OpenXML table for clean letterheads."""
        tblPr = table._tbl.tblPr
        tblBorders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>\n'
            f'  <w:top w:val="none"/>\n'
            f'  <w:left w:val="none"/>\n'
            f'  <w:bottom w:val="none"/>\n'
            f'  <w:right w:val="none"/>\n'
            f'  <w:insideH w:val="none"/>\n'
            f'  <w:insideV w:val="none"/>\n'
            f'</w:tblBorders>'
        )
        tblPr.append(tblBorders)


docx_generator = DocxGeneratorService()
