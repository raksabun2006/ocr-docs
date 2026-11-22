"""
Enterprise Administration API Router
Khmer Government Document Intelligence System

Implements user lifecycle management, role & permission configuration,
audit log queries, OCR statistics, and system health checks.
All endpoints strictly protected by granular database-backed RBAC permissions.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import re
from pydantic import BaseModel, Field, field_validator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import settings
from app.database import get_db
from app.models import (
    User, Role, Permission, UserRole, RolePermission,
    Document, DocumentReview, AuditLog, OCRResult
)
from app.security.password import hash_password, validate_password_strength
from app.security.dependencies import require_permission, get_current_user
from app.services.ocr import get_ocr_provider, _providers

router = APIRouter(prefix="/admin", tags=["Enterprise Administration"])


# ------------------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------------------

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=EMAIL_REGEX)
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8)
    role_names: List[str] = Field(default_factory=lambda: ["VIEWER"])


class UpdateUserRequest(BaseModel):
    email: Optional[str] = Field(None, pattern=EMAIL_REGEX)
    full_name: Optional[str] = None


class UserStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|INACTIVE|LOCKED)$")


class AssignRoleRequest(BaseModel):
    role_names: List[str]


class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = None
    permission_names: List[str] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# Dashboard & Overview
# ------------------------------------------------------------------------------

@router.get("/dashboard")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system.view"))
):
    """Platform-wide operational summary for executive and administrator dashboards."""
    total_users = db.query(User).filter(User.is_deleted == False).count()
    active_users = db.query(User).filter(User.is_deleted == False, User.status == "ACTIVE").count()
    locked_users = db.query(User).filter(User.is_deleted == False, User.status == "LOCKED").count()

    total_docs = db.query(Document).filter(Document.is_deleted == False).count()
    verified_docs = db.query(Document).filter(Document.is_deleted == False, Document.status == "VERIFIED").count()
    pending_docs = db.query(Document).filter(Document.is_deleted == False, Document.status == "PENDING_REVIEW").count()

    total_audits = db.query(AuditLog).count()

    return {
        "success": True,
        "users": {
            "total": total_users,
            "active": active_users,
            "locked": locked_users,
        },
        "documents": {
            "total": total_docs,
            "verified": verified_docs,
            "pending_review": pending_docs,
        },
        "audit_logs_count": total_audits,
        "platform_status": "OPERATIONAL",
    }


# ------------------------------------------------------------------------------
# User Management
# ------------------------------------------------------------------------------

@router.get("/users")
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.view"))
):
    """Lists registered users with roles and current statuses."""
    q = db.query(User).filter(User.is_deleted == False)
    if search:
        s = f"%{search.strip()}%"
        q = q.filter((User.username.ilike(s)) | (User.email.ilike(s)) | (User.full_name.ilike(s)))

    total = q.count()
    users = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    items = []
    for u in users:
        items.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "status": u.status,
            "roles": [r.name for r in u.roles],
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })

    return {"total": total, "items": items, "skip": skip, "limit": limit}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    req: CreateUserRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.create"))
):
    """Creates a new platform user and assigns specified roles."""
    client_ip = request.client.host if request.client else "unknown"

    # 1. Uniqueness check
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Prevent non-superadmins from assigning SUPER_ADMIN role
    current_roles = [r.name for r in current_user.roles]
    if "SUPER_ADMIN" in req.role_names and "SUPER_ADMIN" not in current_roles:
        raise HTTPException(
            status_code=403,
            detail="Only a SUPER_ADMIN may assign the SUPER_ADMIN role"
        )

    # 3. Password strength check
    is_valid, reason = validate_password_strength(req.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=reason)

    # 4. Create user
    new_user = User(
        username=req.username,
        email=req.email,
        full_name=req.full_name,
        password_hash=hash_password(req.password),
        status="ACTIVE",
    )
    db.add(new_user)
    db.flush()

    # 5. Assign roles
    for r_name in req.role_names:
        role = db.query(Role).filter(Role.name == r_name).first()
        if role:
            db.add(UserRole(user_id=new_user.id, role_id=role.id))

    db.add(AuditLog(
        user_id=current_user.id,
        action="USER_CREATED",
        resource_type="USER",
        resource_id=new_user.id,
        ip_address=client_ip,
        details=f"Admin {current_user.username} created user {new_user.username}"
    ))
    db.commit()

    return {"success": True, "user_id": new_user.id, "username": new_user.username}


@router.get("/users/{user_id}")
def get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.view"))
):
    """Retrieves full user details including permissions."""
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    perms = set()
    for r in user.roles:
        for p in r.permissions:
            perms.add(p.code)

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "status": user.status,
        "roles": [r.name for r in user.roles],
        "permissions": sorted(list(perms)),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    req: UpdateUserRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.update"))
):
    """Updates user information."""
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.email and req.email != user.email:
        exist = db.query(User).filter(User.email == req.email, User.id != user_id).first()
        if exist:
            raise HTTPException(status_code=400, detail="Email is already used by another account")
        user.email = req.email

    if req.full_name:
        user.full_name = req.full_name

    db.add(AuditLog(
        user_id=current_user.id,
        action="USER_UPDATED",
        resource_type="USER",
        resource_id=user.id,
        ip_address=request.client.host if request.client else "unknown",
        details=f"Admin {current_user.username} updated user profile {user.username}"
    ))
    db.commit()
    return {"success": True, "message": "User updated successfully"}


@router.patch("/users/{user_id}/status")
def change_user_status(
    user_id: str,
    req: UserStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.disable"))
):
    """Changes user status (ACTIVE, INACTIVE, LOCKED). Prevents disabling the last SUPER_ADMIN."""
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Safety check: Prevent disabling last active SUPER_ADMIN
    if req.status in ("INACTIVE", "LOCKED") and any(r.name == "SUPER_ADMIN" for r in user.roles):
        superadmin_count = (
            db.query(User)
            .join(UserRole, User.id == UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(Role.name == "SUPER_ADMIN", User.status == "ACTIVE", User.is_deleted == False)
            .count()
        )
        if superadmin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Security protection: cannot disable or lock the last active SUPER_ADMIN"
            )

    user.status = req.status
    if req.status == "ACTIVE":
        user.failed_login_attempts = 0
        user.locked_until = None

    db.add(AuditLog(
        user_id=current_user.id,
        action=f"USER_STATUS_{req.status}",
        resource_type="USER",
        resource_id=user.id,
        ip_address=request.client.host if request.client else "unknown",
        details=f"Status of {user.username} changed to {req.status}"
    ))
    db.commit()
    return {"success": True, "status": user.status}


@router.post("/users/{user_id}/roles")
def assign_user_roles(
    user_id: str,
    req: AssignRoleRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.assign_role"))
):
    """Replaces or assigns user roles."""
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    current_roles = [r.name for r in current_user.roles]
    if "SUPER_ADMIN" in req.role_names and "SUPER_ADMIN" not in current_roles:
        raise HTTPException(
            status_code=403,
            detail="Only SUPER_ADMIN users may assign the SUPER_ADMIN role"
        )

    # Clear existing roles
    db.query(UserRole).filter(UserRole.user_id == user.id).delete()

    # Assign requested roles
    for r_name in req.role_names:
        role = db.query(Role).filter(Role.name == r_name).first()
        if role:
            db.add(UserRole(user_id=user.id, role_id=role.id))

    db.add(AuditLog(
        user_id=current_user.id,
        action="USER_ROLES_ASSIGNED",
        resource_type="USER",
        resource_id=user.id,
        ip_address=request.client.host if request.client else "unknown",
        details=f"Assigned roles {req.role_names} to {user.username}"
    ))
    db.commit()
    return {"success": True, "roles": req.role_names}


# ------------------------------------------------------------------------------
# Role & Permission Management
# ------------------------------------------------------------------------------

@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles.view"))
):
    """Lists all configurable roles and their permissions."""
    roles = db.query(Role).all()
    res = []
    for r in roles:
        res.append({
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "is_system": r.is_system,
            "permissions": [p.code for p in r.permissions],
        })
    return {"roles": res}


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles.view"))
):
    """Lists all available granular permissions."""
    perms = db.query(Permission).order_by(Permission.module, Permission.code).all()
    return {
        "permissions": [
            {
                "id": p.id,
                "code": p.code,
                "description": p.description,
                "module": p.module,
            }
            for p in perms
        ]
    }


# ------------------------------------------------------------------------------
# Audit Logs
# ------------------------------------------------------------------------------

@router.get("/audit-logs")
def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit.view"))
):
    """Queries tamper-evident audit logs."""
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)

    total = q.count()
    logs = q.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": l.id,
                "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                "user_id": l.user_id,
                "action": l.action,
                "resource_type": l.resource_type,
                "resource_id": l.resource_id,
                "ip_address": l.ip_address,
                "details": l.details,
            }
            for l in logs
        ],
        "skip": skip,
        "limit": limit,
    }


# ------------------------------------------------------------------------------
# OCR Subsystem & Providers
# ------------------------------------------------------------------------------

@router.get("/ocr/providers")
def list_ocr_providers(
    current_user: User = Depends(require_permission("ocr.manage_settings"))
):
    """Returns status and configuration of registered OCR engines."""
    providers_info = {}
    for name, provider in _providers.items():
        providers_info[name] = provider.get_metadata()

    return {
        "default_provider": settings.DEFAULT_OCR_PROVIDER,
        "providers": providers_info,
    }


@router.get("/ocr/statistics")
def get_ocr_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("ocr.view_results"))
):
    """Returns OCR extraction volume, average confidence, and type distribution."""
    avg_conf = db.query(func.avg(Document.average_confidence)).filter(Document.is_deleted == False).scalar() or 0.0

    types_dist = (
        db.query(Document.document_type, func.count(Document.id))
        .filter(Document.is_deleted == False)
        .group_by(Document.document_type)
        .all()
    )

    return {
        "average_confidence": round(float(avg_conf), 2),
        "document_type_distribution": {t: cnt for t, cnt in types_dist},
    }


# ------------------------------------------------------------------------------
# System Health
# ------------------------------------------------------------------------------

@router.get("/system/health")
def system_health_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system.view"))
):
    """Comprehensive system diagnostic health check."""
    db_ok = True
    try:
        db.execute(func.now())
    except Exception:
        db_ok = False

    tess_provider = _providers.get("TESSERACT")
    tess_ready = tess_provider.is_available() if tess_provider else False

    ollama_provider = _providers.get("OLLAMA")
    ollama_ready = ollama_provider.is_available() if ollama_provider else False

    return {
        "status": "HEALTHY" if db_ok else "DEGRADED",
        "database_connected": db_ok,
        "ocr_tesseract_ready": tess_ready,
        "ocr_ollama_ready": ollama_ready,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
