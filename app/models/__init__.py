from __future__ import annotations

"""
SQLAlchemy Database Models
Khmer Government Document Intelligence Platform

Comprehensive schema supporting:
- RBAC (Users, Roles, Permissions, UserRoles, RolePermissions, TokenRevocation).
- Resource-Level Document Access & Review Tracking.
- Preserved OCR Results (Original OCR vs Human Corrected) & Job Tracking.
- Tamper-Resistant Audit Logging with Data Privacy.
- System Settings & AI Model Configurations.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, JSON, DateTime, ForeignKey, Table, Index
)
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    """Returns the current UTC datetime with timezone awareness."""
    return datetime.now(timezone.utc)


# ==============================================================================
# RBAC Association Tables
# ==============================================================================

class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by = Column(String(100), nullable=True)
    assigned_at = Column(DateTime(timezone=True), default=utc_now)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)


# ==============================================================================
# User, Role, Permission Models
# ==============================================================================

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)  # e.g., 'documents.upload'
    description = Column(String(255), nullable=True)
    module = Column(String(64), nullable=False, index=True)             # e.g., 'documents', 'users'

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, index=True)  # SUPER_ADMIN, ADMIN, etc.
    description = Column(String(255), nullable=True)
    is_system = Column(Boolean, default=True)                           # System roles cannot be deleted

    users = relationship("User", secondary="user_roles", back_populates="roles")
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    password_hash = Column(String(255), nullable=False)

    # Status: ACTIVE, INACTIVE, LOCKED
    status = Column(String(16), default="ACTIVE", index=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    roles = relationship("Role", secondary="user_roles", back_populates="users")
    document_accesses = relationship("DocumentAccess", back_populates="user", cascade="all, delete-orphan")


class TokenRevocation(Base):
    __tablename__ = "token_revocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)


# ==============================================================================
# Document & Resource Access Models
# ==============================================================================

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

    # Workflow Status: UPLOADED, PROCESSING, PROCESSED, PENDING_REVIEW, VERIFIED, REJECTED, FAILED
    status = Column(String(32), default="PENDING", index=True)

    # OCR Extracted Content & Editable Layout Structure
    raw_text = Column(Text, nullable=True)
    original_ocr_output = Column(Text, nullable=True)                   # Immutable original OCR text
    edited_text = Column(Text, nullable=True)                           # User-corrected text
    layout_data = Column(JSON, nullable=True)                           # Detected layout blocks, tables, alignment
    structured_entities = Column(JSON, nullable=True)                   # Administrative entities (Ministry, date, etc.)
    docx_path = Column(String(512), nullable=True)                      # Path to generated editable Word document
    average_confidence = Column(Float, nullable=True)
    uploaded_by = Column(String(100), default="officer")
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_deleted = Column(Boolean, default=False, index=True)             # Soft delete support

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan")
    verifications = relationship("VerificationHistory", back_populates="document", cascade="all, delete-orphan")
    access_grants = relationship("DocumentAccess", back_populates="document", cascade="all, delete-orphan")
    reviews = relationship("DocumentReview", back_populates="document", cascade="all, delete-orphan")
    ocr_results = relationship("OCRResult", back_populates="document", cascade="all, delete-orphan")


class DocumentAccess(Base):
    """Resource-level access control preventing cross-user document access."""
    __tablename__ = "document_access"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    access_level = Column(String(16), default="READ")  # READ, WRITE, REVIEW
    granted_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    document = relationship("Document", back_populates="access_grants")
    user = relationship("User", back_populates="document_accesses")


class DocumentReview(Base):
    """Tracks human reviewer assignments, comments, and decisions."""
    __tablename__ = "document_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id = Column(String(36), nullable=False, index=True)
    reviewer_name = Column(String(100), nullable=False)
    status = Column(String(32), nullable=False)        # PENDING_REVIEW, VERIFIED, REJECTED
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    document = relationship("Document", back_populates="reviews")


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


# ==============================================================================
# OCR Engine & Job Tracking Models
# ==============================================================================

class OCRProcessingJob(Base):
    __tablename__ = "ocr_processing_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)   # TESSERACT, OLLAMA, HYBRID
    model_name = Column(String(64), nullable=True)
    status = Column(String(32), default="PENDING", index=True)  # PENDING, PROCESSING, COMPLETED, FAILED
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("ocr_processing_jobs.id", ondelete="SET NULL"), nullable=True)
    provider = Column(String(32), nullable=False)
    model_name = Column(String(64), nullable=True)
    raw_text = Column(Text, nullable=True)
    original_ocr_output = Column(Text, nullable=True)
    corrected_text = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    preprocessing_strategy = Column(String(64), nullable=True)
    review_status = Column(String(32), default="UNREVIEWED")
    created_at = Column(DateTime(timezone=True), default=utc_now)

    document = relationship("Document", back_populates="ocr_results")


# ==============================================================================
# System Configuration & AI Models
# ==============================================================================

class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AIModelConfig(Base):
    __tablename__ = "ai_model_configurations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)      # e.g., 'glm-ocr', 'qwen2.5vl'
    provider = Column(String(32), default="OLLAMA")
    endpoint_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=False)
    config_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


# ==============================================================================
# Audit Log Model
# ==============================================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    action = Column(String(48), nullable=False, index=True)
    resource_type = Column(String(32), nullable=False, index=True)
    resource_id = Column(String(64), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    outcome = Column(String(16), default="SUCCESS")             # SUCCESS, FAILURE, DENIED
    request_id = Column(String(64), nullable=True)
    details = Column(JSON, nullable=True)                       # Strictly sanitized non-PII metadata
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)
