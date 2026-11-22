"""
Document Classification Service
Khmer Government Document Intelligence System

Classifies scanned Cambodian government documents into official categories:
1. Cambodian birth certificates (សំបុត្រកំណើត)
2. Cambodian family books (សៀវភៅគ្រួសារ)
3. Cambodian identity documents (អត្តសញ្ញាណប័ណ្ណ)
4. Administrative letters (លិខិតរដ្ឋបាល)
5. Government application forms (ពាក្យសុំ)
6. Certificates and other official documents (វិញ្ញាបនបត្រ)
"""

import re
from typing import Dict, List, Tuple
from app.schemas.classification import DocumentTypeEnum, ClassificationResult, DOCUMENT_TYPE_LABELS

# Weighted keywords and regex patterns for each Cambodian document category
CLASSIFICATION_RULES = {
    DocumentTypeEnum.BIRTH_CERTIFICATE: [
        ("សំបុត្រកំណើត", 35.0),
        ("សេចក្តីចម្លងសំបុត្រកំណើត", 40.0),
        ("សំបុត្របញ្ជាក់កំណើត", 40.0),
        ("បញ្ជីជាតិ", 20.0),
        ("គោត្តនាម និង នាម", 20.0),
        ("ថ្ងៃ ខែ ឆ្នាំ កំណើត", 20.0),
        ("ទីកន្លែងកំណើត", 20.0),
        ("ឪពុកឈ្មោះ", 15.0),
        ("ម្តាយឈ្មោះ", 15.0),
        ("birth certificate", 30.0),
    ],
    DocumentTypeEnum.FAMILY_BOOK: [
        ("សៀវភៅគ្រួសារ", 40.0),
        ("សៀវភៅស្នាក់នៅ", 35.0),
        ("ក្បាលសៀវភៅ", 25.0),
        ("មេគ្រួសារ", 30.0),
        ("សមាជិកគ្រួសារ", 25.0),
        ("family book", 35.0),
    ],
    DocumentTypeEnum.IDENTITY_CARD: [
        ("អត្តសញ្ញាណប័ណ្ណ", 35.0),
        ("អត្តសញ្ញាណប័ណ្ណសញ្ជាតិខ្មែរ", 45.0),
        ("លេខអត្តសញ្ញាណ", 25.0),
        ("សុពលភាព", 20.0),
        ("national id", 30.0),
        ("identity card", 30.0),
    ],
    DocumentTypeEnum.ADMINISTRATIVE_LETTER: [
        ("ព្រះរាជាណាចក្រកម្ពុជា", 20.0),
        ("ជាតិ សាសនា ព្រះមហាក្សត្រ", 20.0),
        ("លិខិតរដ្ឋបាល", 35.0),
        ("លិខិតបញ្ជាក់", 25.0),
        ("លិខិតបង្គាប់ការ", 30.0),
        ("លិខិតឧទ្ទេសនាម", 30.0),
        ("ក្រសួង", 15.0),
        ("រដ្ឋបាលរាជធានី", 20.0),
        ("រដ្ឋបាលខេត្ត", 20.0),
        ("កម្មវត្ថុ", 20.0),
        ("យោង", 15.0),
    ],
    DocumentTypeEnum.APPLICATION_FORM: [
        ("ពាក្យសុំ", 35.0),
        ("ពាក្យស្នើសុំ", 40.0),
        ("សូមគោរពជូន", 25.0),
        ("អាស្រ័យហេតុនេះ", 20.0),
        ("ទម្រង់បែបបទ", 25.0),
        ("application form", 30.0),
    ],
    DocumentTypeEnum.OFFICIAL_CERTIFICATE: [
        ("វិញ្ញាបនបត្រ", 35.0),
        ("សញ្ញាបត្រ", 35.0),
        ("លិខិតសរសើរ", 30.0),
        ("បានបញ្ចប់ការសិក្សា", 25.0),
        ("certificate", 30.0),
    ]
}


class DocumentClassifierService:
    """Classifies document content into official Cambodian document types."""

    def classify_text(self, text: str) -> ClassificationResult:
        if not text or not text.strip():
            return ClassificationResult(
                document_type=DocumentTypeEnum.UNKNOWN,
                type_khmer_label=DOCUMENT_TYPE_LABELS[DocumentTypeEnum.UNKNOWN],
                confidence=0.0,
                matched_keywords=[],
                scores={}
            )

        cleaned_text = text.lower()
        scores: Dict[str, float] = {doc_type.value: 0.0 for doc_type in CLASSIFICATION_RULES}
        all_matched_keywords: Dict[str, List[str]] = {doc_type.value: [] for doc_type in CLASSIFICATION_RULES}

        for doc_type, rules in CLASSIFICATION_RULES.items():
            for keyword, weight in rules:
                pattern = re.escape(keyword.lower())
                if re.search(pattern, cleaned_text):
                    scores[doc_type.value] += weight
                    all_matched_keywords[doc_type.value].append(keyword)

        best_type_str = max(scores, key=scores.get)
        best_score = scores[best_type_str]

        if best_score < 30.0:
            return ClassificationResult(
                document_type=DocumentTypeEnum.UNKNOWN,
                type_khmer_label=DOCUMENT_TYPE_LABELS[DocumentTypeEnum.UNKNOWN],
                confidence=0.0,
                matched_keywords=[],
                scores={k: round(v, 2) for k, v in scores.items()}
            )

        confidence = min(round((best_score / 80.0) * 100.0, 2), 99.0)
        best_doc_type = DocumentTypeEnum(best_type_str)

        return ClassificationResult(
            document_type=best_doc_type,
            type_khmer_label=DOCUMENT_TYPE_LABELS[best_doc_type],
            confidence=confidence,
            matched_keywords=all_matched_keywords[best_type_str],
            scores={k: round(v, 2) for k, v in scores.items()}
        )


classifier_service = DocumentClassifierService()
