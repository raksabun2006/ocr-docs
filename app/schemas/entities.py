"""
Government Administrative Document Entity Schemas
Khmer Government Document Intelligence System
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SignerInfo(BaseModel):
    name: Optional[str] = None
    role_title: Optional[str] = None
    organization: Optional[str] = None


class GovernmentEntityData(BaseModel):
    """Structured fields extracted from administrative documents."""
    ministry: Optional[str] = Field(None, description="Ministry, Secretariat, or Institution name")
    department: Optional[str] = Field(None, description="General Department, Department, or Office")
    document_number: Optional[str] = Field(None, description="Official registration number e.g. លេខ : ១២៣/២៤")
    location: Optional[str] = Field(None, description="Location of issuance e.g. រាជធានីភ្នំពេញ")
    document_date: Optional[str] = Field(None, description="Official date of issuance")
    document_title: Optional[str] = Field(None, description="Document title or declaration subject")
    recipient: Optional[str] = Field(None, description="Recipient e.g. សូមគោរពជូន ឯកឧត្តម...")
    sender: Optional[str] = Field(None, description="Issuing entity or official sender")
    subject: Optional[str] = Field(None, description="Subject statement e.g. កម្មវត្ថុ")
    references: List[str] = Field(default_factory=list, description="Legal references e.g. យោង")
    main_content: Optional[str] = Field(None, description="Core substantive paragraphs")
    signers: List[SignerInfo] = Field(default_factory=list, description="Signing officials and titles")
    tables_detected: int = Field(0, description="Number of detected structured tables")
    metadata: Dict[str, Any] = Field(default_factory=dict)
