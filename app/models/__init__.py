"""
SQLAlchemy Models for Khmer Government Document Intelligence System
Tables:
- Document
- ExtractedField
- VerificationHistory
- AuditLog
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, JSON, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    mime_type = Column(String(64), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)

    # Document Classification
    document_type = Column(String(64), default="UNKNOWN", index=True)
    is_classified_by_user = Column(Boolean, default=False)

    # Workflow Status: PENDING, PROCESSED, VERIFIED, REJECTED
    status = Column(String(32), default="PENDING", index=True)

    # OCR Extracted Content
    raw_text = Column(Text, nullable=True)
    average_confidence = Column(Float, nullable=True)
    uploaded_by = Column(String(100), default="officer")

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    extracted_fields = relationship(
        "ExtractedField",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    verifications = relationship(
        "VerificationHistory",
        back_populates="document",
        cascade="all, delete-orphan"
    )


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(64), nullable=False, index=True)
    field_value = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    bounding_box = Column(JSON, nullable=True)
    is_verified = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    document = relationship("Document", back_populates="extracted_fields")


class VerificationHistory(Base):
    __tablename__ = "verification_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(64), nullable=False)
    original_value = Column(Text, nullable=True)
    corrected_value = Column(Text, nullable=True)
    verified_by = Column(String(100), nullable=False)
    notes = Column(Text, nullable=True)
    verified_at = Column(DateTime(timezone=True), default=utc_now)

    document = relationship("Document", back_populates="verifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    action = Column(String(32), nullable=False, index=True)  # UPLOAD, VIEW, EDIT, VERIFY, CLASSIFY, EXPORT, DELETE
    resource_type = Column(String(32), nullable=False)       # DOCUMENT, EXTRACTED_FIELD, USER
    resource_id = Column(String(64), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(JSON, nullable=True)                    # Strictly sanitized non-PII details
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)
