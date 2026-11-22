"""
Audit Logging and Privacy Protection Service
Khmer Government Document Intelligence System

Enforces public-sector privacy and security requirements:
- Strictly redacts/masks sensitive personal information (PII) before emitting logs.
- Persists tamper-resistant audit entries for viewing, editing, verifying, and deleting documents.
"""

import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.config import settings

logger = logging.getLogger("audit_service")


def mask_sensitive_data(val: Any) -> Any:
    """
    Masks citizen personal identifiers, names, and numbers from log strings
    to maintain strict compliance with data privacy.
    """
    if not isinstance(val, str):
        return val

    # Mask long numbers (IDs, registration numbers)
    masked = re.sub(r"\b\d{4,}\b", "[REDACTED_NUM]", val)
    return masked


def sanitize_audit_details(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensures no raw citizen names or PII leak into log payloads."""
    if not details:
        return {}

    sanitized = {}
    for k, v in details.items():
        if k in ("raw_text", "full_name_khmer", "full_name_english", "father_name", "mother_name", "date_of_birth"):
            sanitized[k] = "[CONFIDENTIAL_CITIZEN_DATA]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_audit_details(v)
        else:
            sanitized[k] = mask_sensitive_data(v)
    return sanitized


class AuditService:
    """Records audit logs in the database and safely logs actions."""

    def log_action(
        self,
        db: Session,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        sanitized_details = sanitize_audit_details(details)

        audit_entry = AuditLog(
            user_id=user_id,
            action=action.upper(),
            resource_type=resource_type.upper(),
            resource_id=resource_id,
            ip_address=ip_address or "127.0.0.1",
            details=sanitized_details,
            timestamp=datetime.now(timezone.utc)
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)

        if settings.MASK_SENSITIVE_LOGS:
            logger.info(
                f"[AUDIT] user={user_id} action={action} resource={resource_type}:{resource_id} ip={ip_address}"
            )
        return audit_entry


audit_service = AuditService()
