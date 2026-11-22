"""
Audit Log Schemas
Khmer Government Document Intelligence System
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class AuditLogItem(BaseModel):
    id: int
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    ip_address: Optional[str]
    details: Optional[Dict[str, Any]]
    timestamp: datetime


class AuditLogQueryResponse(BaseModel):
    total: int
    items: List[AuditLogItem]
