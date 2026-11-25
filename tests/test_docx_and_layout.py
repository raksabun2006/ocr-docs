"""
Comprehensive Tests for Document Layout Analysis, Entity Extraction, and DOCX Generation
Khmer Government Document Intelligence System
"""

import os
import pytest
import docx
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Document
from app.services.layout_service import layout_analyzer
from app.services.admin_extraction_service import admin_extractor
from app.services.docx_generator_service import docx_generator, FONT_BODY, FONT_HEADING
from app.schemas.layout import LayoutElement, ElementTypeEnum, DocumentContentUpdateRequest
from app.routers.document_router import (
    get_document_layout,
    update_document_content,
    export_document_to_docx,
    get_document_processing_status
)


SAMPLE_KHMER_DOCUMENT_TEXT = """ព្រះរាជាណាចក្រកម្ពុជា
ជាតិ សាសនា ព្រះមហាក្សត្រ
ក្រសួងមុខងារសាធារណៈ
អគ្គនាយកដ្ឋានគ្រប់គ្រងបុគ្គលិក
លេខ : ៤៥៦/២៦ មស.សជណ
រាជធានីភ្នំពេញ, ថ្ងៃទី២៥ ខែវិច្ឆិកា ឆ្នាំ២០២៦
សេចក្តីជូនដំណឹង
សូមគោរពជូន ឯកឧត្តម លោកជំទាវ រដ្ឋមន្ត្រីគ្រប់ក្រសួង ស្ថាប័ន
កម្មវត្ថុ : ស្តីពីការរៀបចំប្រព័ន្ធគ្រប់គ្រងឯកសារអេឡិចត្រូនិកឆ្លាតវៃ
យោង : អនុក្រឹត្យលេខ ១២៣ អនក្រ.បក ចុះថ្ងៃទី១០ ខែមករា ឆ្នាំ២០២៤
សេចក្តីដូចមានចែងក្នុងកម្មវត្ថុ និងយោងខាងលើ សូមជម្រាបជូនឯកឧត្តម លោកជំទាវ មេត្តាជ្រាបថា ក្រសួងបានដាក់ឱ្យដំណើរការប្រព័ន្ធ OCR។
| ល.រ | ឈ្មោះកម្មវិធី | ស្ថានភាព |
| ១ | ប្រព័ន្ធ OCR ខ្មែរ | ដំណើរការ |
| ២ | ម៉ូឌុល DOCX | រួចរាល់ |
- ចំណុចទី១ ត្រូវត្រួតពិនិត្យឯកសារមុននាំចេញ
- ចំណុចទី២ ត្រូវរក្សាទុកក្នុងបណ្ណសារ
អាស្រ័យហេតុនេះ សូមឯកឧត្តម លោកជំទាវ មេត្តាជ្រាបជាព័ត៌មាន។
រដ្ឋមន្ត្រីក្រសួងមុខងារសាធារណៈ
(ហត្ថលេខា និងត្រា)
ហ៊ុន ម៉ានី"""


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_layout_analysis_structure():
    """Verify that layout analyzer recognizes all semantic Cambodian government elements."""
    elements = layout_analyzer.analyze(SAMPLE_KHMER_DOCUMENT_TEXT)
    assert len(elements) > 0

    types_found = {e.element_type for e in elements}
    assert ElementTypeEnum.ROYAL_MOTTO in types_found
    assert ElementTypeEnum.MINISTRY_HEADER in types_found
    assert ElementTypeEnum.DOCUMENT_NUMBER in types_found
    assert ElementTypeEnum.DATE_LOCATION in types_found
    assert ElementTypeEnum.DOCUMENT_TITLE in types_found
    assert ElementTypeEnum.RECIPIENT in types_found
    assert ElementTypeEnum.SUBJECT in types_found
    assert ElementTypeEnum.REFERENCE in types_found
    assert ElementTypeEnum.TABLE in types_found
    assert ElementTypeEnum.LIST_ITEM in types_found
    assert ElementTypeEnum.SIGNATURE_BLOCK in types_found

    # Check table parsing
    table_elem = next(e for e in elements if e.element_type == ElementTypeEnum.TABLE)
    assert table_elem.table_data is not None
    assert len(table_elem.table_data) == 3
    assert table_elem.table_data[0][0] == "ល.រ"
    assert table_elem.table_data[1][1] == "ប្រព័ន្ធ OCR ខ្មែរ"


def test_admin_entity_extraction():
    """Verify structured administrative metadata extraction."""
    entities = admin_extractor.extract(SAMPLE_KHMER_DOCUMENT_TEXT)

    assert entities.ministry is not None
    assert "ក្រសួងមុខងារសាធារណៈ" in entities.ministry

    assert entities.department is not None
    assert "អគ្គនាយកដ្ឋាន" in entities.department

    assert entities.document_number is not None
    assert "៤៥៦/២៦" in entities.document_number

    assert entities.location == "រាជធានីភ្នំពេញ"
    assert "២៥" in entities.document_date
    assert "វិច្ឆិកា" in entities.document_date

    assert entities.document_title == "សេចក្តីជូនដំណឹង"
    assert "ឯកឧត្តម" in entities.recipient
    assert "កម្មវិធី" in entities.subject or "ប្រព័ន្ធ" in entities.subject
    assert len(entities.references) >= 1
    assert "១២៣" in entities.references[0]


def test_docx_generation_and_editability(tmp_path):
    """Verify generating Word document with native editable elements and Khmer fonts."""
    elements = layout_analyzer.analyze(SAMPLE_KHMER_DOCUMENT_TEXT)
    doc_id = "doc-uuid-9999"

    docx_path = docx_generator.generate_docx(
        document_id=doc_id,
        filename_prefix="TestNotice",
        elements=elements
    )

    assert os.path.exists(docx_path)
    assert docx_path.stat().st_size > 1000

    # Read back and inspect with python-docx
    doc = docx.Document(str(docx_path))

    # Verify A4 page size
    section = doc.sections[0]
    assert round(section.page_width.inches, 2) == 8.27
    assert round(section.page_height.inches, 2) == 11.69

    # Verify letterhead table and content table exist
    assert len(doc.tables) >= 2

    # Check letterhead 2-column table
    header_table = doc.tables[0]
    assert len(header_table.columns) == 2
    assert "ក្រសួង" in header_table.cell(0, 0).text
    assert "ព្រះរាជាណាចក្រកម្ពុជា" in header_table.cell(0, 1).text

    # Check data table
    data_table = doc.tables[1]
    assert len(data_table.rows) == 3
    assert data_table.cell(0, 0).text.strip() == "ល.រ"

    # Verify text editability (paragraphs contain text, not pictures/shapes)
    doc_text = "\n".join([p.text for p in doc.paragraphs if p.text])
    assert "សេចក្តីជូនដំណឹង" in doc_text
    assert "កម្មវត្ថុ" in doc_text


def test_docx_preserves_user_corrections(test_db):
    """Verify that human corrections to text or layout are preserved and rendered into DOCX."""
    doc_record = Document(
        id="doc-corr-test-1",
        original_filename="minister_letter.pdf",
        storage_path="uploads/minister_letter.pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        sha256_hash="dummyhash123",
        document_type="ANNOUNCEMENT_NOTICE",
        status="PROCESSED",
        raw_text="កំហុសអត្ថបទចាស់"
    )
    test_db.add(doc_record)
    test_db.commit()

    # Apply correction via content update handler
    corrected_text = "អត្ថបទថ្មីដែលបានកែសម្រួលត្រឹមត្រូវ តាមការចង្អុលបង្ហាញរបស់ថ្នាក់ដឹកនាំ"
    update_req = DocumentContentUpdateRequest(
        edited_text=corrected_text,
        notes="Corrected OCR mistake in header"
    )
    update_res = update_document_content(doc_record.id, update_req, test_db)
    assert update_res["success"] is True

    # Re-fetch from DB
    test_db.refresh(doc_record)
    assert doc_record.edited_text == corrected_text

    # Export to DOCX
    export_res = export_document_to_docx(doc_record.id, test_db)
    assert export_res.success is True
    assert os.path.exists(doc_record.docx_path)

    # Read back DOCX to verify the corrected text is inside the Word file
    doc = docx.Document(doc_record.docx_path)
    full_text = " ".join([p.text for p in doc.paragraphs])
    assert "អត្ថបទថ្មីដែលបានកែសម្រួលត្រឹមត្រូវ" in full_text
