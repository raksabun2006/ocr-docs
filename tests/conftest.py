"""
Test Fixtures and Helpers
Khmer Government Document Intelligence System
"""

import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
import io
import pytest
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# Isolated In-Memory SQLite Engine for Testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# Helper to get an available font
def get_khmer_or_default_font(size: int = 24):
    for f in [
        r"C:\Windows\Fonts\KhmerOSsys.ttf",
        r"C:\Windows\Fonts\KhmerUI.ttf",
        r"C:\Windows\Fonts\daunpenh.ttf",
        r"C:\Windows\Fonts\LeelawUI.ttf"
    ]:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                pass
    return ImageFont.load_default()


@pytest.fixture
def english_receipt_bytes() -> bytes:
    """Generates real image bytes for an English document/receipt."""
    img = Image.new("RGB", (500, 300), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((30, 30), "OFFICIAL RECEIPT", fill="black", font=font)
    draw.text((30, 70), "Document Processing Fee", fill="black", font=font)
    draw.text((30, 110), "Amount: $10.00", fill="black", font=font)
    draw.text((30, 150), "Receipt No: REC-98765", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def khmer_document_bytes() -> bytes:
    """Generates real image bytes for a Khmer government document."""
    img = Image.new("RGB", (650, 350), color="white")
    draw = ImageDraw.Draw(img)
    font = get_khmer_or_default_font(26)
    draw.text((50, 30), "ព្រះរាជាណាចក្រកម្ពុជា", fill="black", font=font)
    draw.text((50, 70), "ជាតិ សាសនា ព្រះមហាក្សត្រ", fill="black", font=font)
    draw.text((50, 110), "លិខិតរដ្ឋបាល", fill="black", font=font)
    draw.text((50, 150), "កម្មវត្ថុ : ការស្នើសុំឯកសាររដ្ឋបាល", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mixed_birth_certificate_bytes() -> bytes:
    """Generates real image bytes for a Mixed English + Khmer Birth Certificate."""
    img = Image.new("RGB", (750, 480), color="white")
    draw = ImageDraw.Draw(img)
    font = get_khmer_or_default_font(24)
    draw.text((150, 20), "ព្រះរាជាណាចក្រកម្ពុជា", fill="black", font=font)
    draw.text((180, 55), "ជាតិ សាសនា ព្រះមហាក្សត្រ", fill="black", font=font)
    draw.text((160, 95), "សេចក្តីចម្លងសំបុត្រកំណើត", fill="black", font=font)
    draw.text((200, 130), "BIRTH CERTIFICATE", fill="black", font=font)
    draw.line([(30, 165), (720, 165)], fill="black", width=2)
    draw.text((40, 185), "គោត្តនាម និង នាម : សុខ សាន", fill="black", font=font)
    draw.text((40, 225), "In Latin : SOK SAN", fill="black", font=font)
    draw.text((40, 265), "ភេទ : ប្រុស (MALE)", fill="black", font=font)
    draw.text((40, 305), "កើតថ្ងៃទី : ១៥ ខែ មេសា ឆ្នាំ ២០០០ (15-04-2000)", fill="black", font=font)
    draw.text((40, 345), "ទីកន្លែងកំណើត : រាជធានីភ្នំពេញ", fill="black", font=font)
    draw.text((40, 385), "ឪពុកឈ្មោះ : សុខ មករា", fill="black", font=font)
    draw.text((40, 425), "លេខសំបុត្រ : 1234/2000", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def corrupted_image_bytes() -> bytes:
    """Bytes starting with PNG magic header but containing broken data."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x01\x02CORRUPTED_STREAM" * 20


@pytest.fixture
def non_image_text_bytes() -> bytes:
    """Plain text file pretending to be an image."""
    return b"This is just a text file, not a valid document image."


@pytest.fixture
def oversized_image_bytes() -> bytes:
    """Generates bytes exceeding 15MB."""
    # 16 MB of data starting with JPEG magic
    return b"\xFF\xD8\xFF" + b"\x00" * (16 * 1024 * 1024)
