"""
Test API Endpoints End-to-End
"""

import io
import pytest
from app.models import Document, ExtractedField


def test_root_endpoint(client):
    """Verify health and API status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "ocr_engine" in data
    assert data["docs_url"] == "/docs"


def test_upload_valid_document(client, mixed_birth_certificate_bytes):
    """Test successful document upload, OCR, and classification."""
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("birth_cert.png", mixed_birth_certificate_bytes, "image/png")},
        data={"officer_name": "officer_test"}
    )
    assert response.status_code == 201
    data = response.json()
    assert "document_id" in data
    assert data["original_filename"] == "birth_cert.png"
    assert data["document_type"] == "BIRTH_CERTIFICATE"
    assert data["status"] in ("PROCESSED", "PENDING")


def test_upload_oversized_file(client, oversized_image_bytes):
    """Test rejecting file exceeding maximum size limit (15MB) with HTTP 413."""
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("huge_doc.jpg", oversized_image_bytes, "image/jpeg")}
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"].lower()


def test_upload_invalid_extension(client):
    """Test rejecting disallowed extensions."""
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("malicious.exe", b"MZ\x90\x00\x03Executable", "application/x-msdownload")}
    )
    assert response.status_code == 400


def test_upload_corrupted_image(client, corrupted_image_bytes):
    """Test safe handling of corrupted image files."""
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("corrupt.png", corrupted_image_bytes, "image/png")}
    )
    assert response.status_code == 400
    assert "corrupted" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()


def test_human_verification_workflow(client, db_session):
    """Test human verification view, uncertainty highlighting, and confirmed submission."""
    # Seed document with extracted field
    doc = Document(
        id="test-doc-uuid",
        original_filename="sample.png",
        storage_path="uploads/documents/test-doc-uuid.png",
        mime_type="image/png",
        file_size_bytes=1000,
        sha256_hash="dummyhash",
        document_type="BIRTH_CERTIFICATE",
        status="PROCESSED"
    )
    db_session.add(doc)
    field = ExtractedField(
        document_id="test-doc-uuid",
        field_name="full_name_khmer",
        field_value="សុខ សាន",
        confidence=45.0,  # Below 50% => high uncertainty
        is_verified=False
    )
    db_session.add(field)
    db_session.commit()

    # 1. Get verification view
    resp = client.get("/api/v1/verifications/test-doc-uuid")
    assert resp.status_code == 200
    v_data = resp.json()
    assert v_data["document_id"] == "test-doc-uuid"
    assert "full_name_khmer" in v_data["highlighted_uncertain_fields"]

    # 2. Submit without confirmation -> Should fail
    fail_resp = client.post(
        "/api/v1/verifications/test-doc-uuid/submit",
        json={
            "reviewer_name": "Officer Meng",
            "corrections": [{"field_name": "full_name_khmer", "corrected_value": "សុខ សាន្ត"}],
            "confirm_and_finalize": False
        }
    )
    assert fail_resp.status_code == 400
    assert "mandatory" in fail_resp.json()["detail"].lower()

    # 3. Submit with confirmation -> Succeeds
    success_resp = client.post(
        "/api/v1/verifications/test-doc-uuid/submit",
        json={
            "reviewer_name": "Officer Meng",
            "corrections": [{"field_name": "full_name_khmer", "corrected_value": "សុខ សាន្ត"}],
            "confirm_and_finalize": True,
            "notes": "Corrected Khmer spelling"
        }
    )
    assert success_resp.status_code == 200
    res_data = success_resp.json()
    assert res_data["status"] == "VERIFIED"
    assert res_data["total_corrected_fields"] == 1


def test_archive_search(client, db_session):
    """Test digital archive search functionality."""
    doc = Document(
        id="search-doc-uuid",
        original_filename="khmer_letter.png",
        storage_path="uploads/documents/search-doc-uuid.png",
        mime_type="image/png",
        file_size_bytes=2000,
        sha256_hash="dummysearchhash",
        document_type="ADMINISTRATIVE_LETTER",
        status="PROCESSED",
        raw_text="ព្រះរាជាណាចក្រកម្ពុជា លិខិតរដ្ឋបាល ក្រសួងមហាផ្ទៃ"
    )
    db_session.add(doc)
    db_session.commit()

    # Search by keyword
    resp = client.get("/api/v1/archive/search?query=ក្រសួងមហាផ្ទៃ")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["document_id"] == "search-doc-uuid"


def test_receipt_scan_endpoint_compatibility(client, english_receipt_bytes):
    """Verify backward compatibility endpoint POST /api/v1/receipts/scan."""
    response = client.post(
        "/api/v1/receipts/scan",
        files={"file": ("receipt.png", english_receipt_bytes, "image/png")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["filename"] == "receipt.png"
    assert data["languages"] == ["eng", "khm"]
    assert "extracted_text" in data
