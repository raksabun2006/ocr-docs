"""
Audit Logs Router
Khmer Government Document Intelligence System
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog
from app.schemas.audit_log import AuditLogQueryResponse, AuditLogItem

router = APIRouter(prefix="/audit", tags=["Security & Audit"])


@router.get("/logs", response_model=AuditLogQueryResponse)
def get_audit_trail(
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Returns audit trail logs for administrative accountability.
    Strictly masks any citizen PII.
    """
    query = db.query(AuditLog)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action.upper())
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)

    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    items = [
        AuditLogItem(
            id=l.id,
            user_id=l.user_id,
            action=l.action,
            resource_type=l.resource_type,
            resource_id=l.resource_id,
            ip_address=l.ip_address,
            details=l.details,
            timestamp=l.timestamp
        )
        for l in logs
    ]

    return AuditLogQueryResponse(total=total, items=items)
