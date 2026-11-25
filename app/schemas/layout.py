"""
Document Layout Analysis & Editable Content Schemas
Khmer Government Document Intelligence System
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ElementTypeEnum(str, Enum):
    ROYAL_MOTTO = "ROYAL_MOTTO"                 # ព្រះរាជាណាចក្រកម្ពុជា / ជាតិ សាសនា ព្រះមហាក្សត្រ
    MINISTRY_HEADER = "MINISTRY_HEADER"         # ក្រសួង... / រដ្ឋបាលរាជធានី...
    DOCUMENT_NUMBER = "DOCUMENT_NUMBER"         # លេខ : ... / លិខិតលេខ ...
    DATE_LOCATION = "DATE_LOCATION"             # រាជធានីភ្នំពេញ ថ្ងៃទី...
    DOCUMENT_TITLE = "DOCUMENT_TITLE"           # ចំណងជើង (សេចក្តីជូនដំណឹង, សេចក្តីសម្រេច, លិខិត...)
    RECIPIENT = "RECIPIENT"                     # សូមគោរពជូន... / ផ្ញើជូន...
    SENDER = "SENDER"                           # ពី...
    SUBJECT = "SUBJECT"                         # កម្មវត្ថុ : ...
    REFERENCE = "REFERENCE"                     # យោង : ...
    PARAGRAPH = "PARAGRAPH"                     # កថាខណ្ឌខ្លឹមសារ
    LIST_ITEM = "LIST_ITEM"                     # ចំណុចរាយ / បញ្ជី
    TABLE = "TABLE"                             # តារាង
    SIGNATURE_BLOCK = "SIGNATURE_BLOCK"         # ហត្ថលេខា និងត្រា (ស្ដាំ/ឆ្វេង)
    FOOTER = "FOOTER"                           # បាតទំព័រ / អាសយដ្ឋាន
    UNKNOWN = "UNKNOWN"


class BoundingBox(BaseModel):
    x: int = Field(0, description="Left coordinate in pixels")
    y: int = Field(0, description="Top coordinate in pixels")
    width: int = Field(0, description="Width in pixels")
    height: int = Field(0, description="Height in pixels")


class LayoutTableCell(BaseModel):
    text: str
    row_idx: int
    col_idx: int
    is_header: bool = False


class LayoutElement(BaseModel):
    id: str
    element_type: ElementTypeEnum
    text: str
    page_number: int = 1
    bounding_box: Optional[BoundingBox] = None
    confidence: float = 0.0
    alignment: str = "left"                     # left, center, right, justify
    font_weight: str = "normal"                 # normal, bold
    is_heading: bool = False
    table_data: Optional[List[List[str]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentLayoutResponse(BaseModel):
    document_id: str
    total_pages: int = 1
    elements: List[LayoutElement]
    raw_text: str
    edited_text: Optional[str] = None
    confidence: float = 0.0


class DocumentContentUpdateRequest(BaseModel):
    edited_text: Optional[str] = Field(None, description="Full corrected Khmer text content")
    elements: Optional[List[LayoutElement]] = Field(None, description="Updated layout elements")
    notes: Optional[str] = Field(None, description="Correction notes by reviewer")


class DocxExportResponse(BaseModel):
    success: bool
    document_id: str
    filename: str
    download_url: str
    file_size_bytes: int
    page_count: int
    created_at: datetime
