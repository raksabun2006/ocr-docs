"""
Test Document Classification Service
"""

import pytest
from app.services.classifier_service import classifier_service
from app.schemas.classification import DocumentTypeEnum


def test_classify_birth_certificate():
    text = "ព្រះរាជាណាចក្រកម្ពុជា សេចក្តីចម្លងសំបុត្រកំណើត គោត្តនាម និង នាម ថ្ងៃ ខែ ឆ្នាំ កំណើត"
    result = classifier_service.classify_text(text)
    assert result.document_type == DocumentTypeEnum.BIRTH_CERTIFICATE
    assert result.confidence > 50.0


def test_classify_family_book():
    text = "ព្រះរាជាណាចក្រកម្ពុជា សៀវភៅគ្រួសារ ក្បាលសៀវភៅ មេគ្រួសារ សមាជិកគ្រួសារ"
    result = classifier_service.classify_text(text)
    assert result.document_type == DocumentTypeEnum.FAMILY_BOOK
    assert result.confidence > 50.0


def test_classify_identity_card():
    text = "អត្តសញ្ញាណប័ណ្ណសញ្ជាតិខ្មែរ លេខអត្តសញ្ញាណ សុពលភាព national id"
    result = classifier_service.classify_text(text)
    assert result.document_type == DocumentTypeEnum.IDENTITY_CARD
    assert result.confidence > 50.0


def test_classify_administrative_letter():
    text = "ព្រះរាជាណាចក្រកម្ពុជា ជាតិ សាសនា ព្រះមហាក្សត្រ ក្រសួងមហាផ្ទៃ លិខិតរដ្ឋបាល លិខិតបញ្ជាក់ កម្មវត្ថុ យោង"
    result = classifier_service.classify_text(text)
    assert result.document_type == DocumentTypeEnum.ADMINISTRATIVE_LETTER
    assert result.confidence > 50.0


def test_classify_application_form():
    text = "ព្រះរាជាណាចក្រកម្ពុជា ពាក្យស្នើសុំ សូមគោរពជូន អាស្រ័យហេតុនេះ ទម្រង់បែបបទ"
    result = classifier_service.classify_text(text)
    assert result.document_type == DocumentTypeEnum.APPLICATION_FORM


def test_classify_unknown_or_blank():
    text = "random text without any government keywords 12345"
    result = classifier_service.classify_text(text)
    assert result.document_type == DocumentTypeEnum.UNKNOWN
    assert result.confidence == 0.0
