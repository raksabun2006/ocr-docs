"""
Unit Tests for Authentication, Password Security, RBAC & Resource Authorization
Khmer Government Document Intelligence System
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User, Role, Permission, Document, DocumentAccess, DocumentReview, TokenRevocation
from app.security.password import hash_password, verify_password, validate_password_strength
from app.security.tokens import create_access_token, decode_access_token
from app.security.seeder import seed_roles_and_permissions
from app.security.dependencies import get_user_permissions, validate_document_access
from fastapi import HTTPException


@pytest.fixture(scope="module")
def rbac_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed standard permissions and roles
    seed_roles_and_permissions(session)

    yield session
    session.close()


def test_password_policy():
    """Verify strict password strength requirements."""
    # Too short
    valid, _ = validate_password_strength("Short1!")
    assert valid is False
    # No digit
    valid, _ = validate_password_strength("NoDigitHere!")
    assert valid is False
    # No special char
    valid, _ = validate_password_strength("NoSpecialChar123")
    assert valid is False
    # No uppercase
    valid, _ = validate_password_strength("lowercase_only_123!")
    assert valid is False
    # Valid secure password
    valid, _ = validate_password_strength("SecureAdmin#2026")
    assert valid is True


def test_password_hashing():
    """Verify cryptographically secure password hashing and verification."""
    password = "CorrectHorseBatteryStaple!2026"
    pwd_hash = hash_password(password)

    assert pwd_hash != password
    assert verify_password(password, pwd_hash) is True
    assert verify_password("WrongPassword123!", pwd_hash) is False


def test_jwt_token_creation_and_decoding():
    """Verify HS256 JWT generation and validation."""
    payload_data = {
        "sub": "user-uuid-1234",
        "username": "officer_sophat",
        "roles": ["OCR_OPERATOR"],
        "permissions": ["documents.upload", "ocr.process"]
    }
    token = create_access_token(payload_data, expires_delta_seconds=1800)

    assert token is not None

    decoded = decode_access_token(token)
    assert decoded["sub"] == "user-uuid-1234"
    assert decoded["username"] == "officer_sophat"
    assert "OCR_OPERATOR" in decoded["roles"]
    assert "documents.upload" in decoded["permissions"]
    assert "jti" in decoded


def test_rbac_seeder_roles_and_permissions(rbac_db):
    """Verify that seeder properly initializes all roles and permissions."""
    super_admin = rbac_db.query(Role).filter(Role.name == "SUPER_ADMIN").first()
    admin = rbac_db.query(Role).filter(Role.name == "ADMIN").first()
    operator = rbac_db.query(Role).filter(Role.name == "OCR_OPERATOR").first()
    reviewer = rbac_db.query(Role).filter(Role.name == "REVIEWER").first()
    viewer = rbac_db.query(Role).filter(Role.name == "VIEWER").first()

    assert super_admin is not None
    assert admin is not None
    assert operator is not None
    assert reviewer is not None
    assert viewer is not None

    # Check permission assignments
    operator_perms = {p.code for p in operator.permissions}
    assert "documents.upload" in operator_perms
    assert "ocr.process" in operator_perms
    assert "system.manage" not in operator_perms

    reviewer_perms = {p.code for p in reviewer.permissions}
    assert "verification.review" in reviewer_perms
    assert "verification.approve" in reviewer_perms


def test_resource_level_document_access(rbac_db):
    """Verify resource-level access control preventing unauthorized cross-user access."""
    # Create two test users
    user_a = User(
        username="officer_a",
        email="officer_a@gov.kh",
        full_name="Officer A",
        password_hash=hash_password("PassA#1234"),
        status="ACTIVE"
    )
    user_b = User(
        username="officer_b",
        email="officer_b@gov.kh",
        full_name="Officer B",
        password_hash=hash_password("PassB#1234"),
        status="ACTIVE"
    )
    rbac_db.add_all([user_a, user_b])
    rbac_db.flush()

    # Assign OCR_OPERATOR role to both
    operator_role = rbac_db.query(Role).filter(Role.name == "OCR_OPERATOR").first()
    user_a.roles.append(operator_role)
    user_b.roles.append(operator_role)

    # Document owned by user_a
    doc = Document(
        id="doc-test-secret-101",
        original_filename="confidential_letter.pdf",
        storage_path="uploads/confidential_letter.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        sha256_hash="dummyhash101",
        uploaded_by="officer_a",
        user_id=user_a.id,
        status="PROCESSED"
    )
    rbac_db.add(doc)
    rbac_db.commit()

    # 1. Creator (user_a) has access
    accessed_doc = validate_document_access(doc.id, user_a, rbac_db)
    assert accessed_doc.id == doc.id

    # 2. Unrelated user (user_b) is denied access
    with pytest.raises(HTTPException) as exc_info:
        validate_document_access(doc.id, user_b, rbac_db)
    assert exc_info.value.status_code == 403

    # 3. Explicit DocumentAccess grant allows access to user_b
    access_grant = DocumentAccess(
        document_id=doc.id,
        user_id=user_b.id,
        access_level="READ",
        granted_by="officer_a"
    )
    rbac_db.add(access_grant)
    rbac_db.commit()

    granted_doc = validate_document_access(doc.id, user_b, rbac_db)
    assert granted_doc.id == doc.id
