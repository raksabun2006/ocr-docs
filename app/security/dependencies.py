from __future__ import annotations

"""
Authentication & Authorization Dependencies
Khmer Government Document Intelligence Platform

Enforces:
- Bearer JWT token verification.
- Active user status checks (rejection of INACTIVE or LOCKED accounts).
- Granular Role-Based Access Control (RBAC).
- Resource-level authorization preventing cross-user document tampering.
"""

from typing import List, Optional, Callable
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Role, Permission, Document, DocumentAccess, DocumentReview
from app.security.tokens import decode_access_token

security_scheme = HTTPBearer(auto_error=False)


def get_token_from_header(request: Request) -> Optional[str]:
    """Extracts raw Bearer token from the incoming Request Authorization header."""
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Validates JWT Bearer token and returns the authenticated User.
    Ensures account status is ACTIVE and not LOCKED.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(err)}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token: missing subject.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if user.status == "LOCKED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been temporarily locked due to security policy violations."
        )

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is inactive ({user.status}). Contact an administrator."
        )

    return user


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Returns authenticated user if a valid token is provided, or None.
    Maintains backward compatibility with unauthenticated legacy endpoints.
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


def get_user_permissions(user: User, db: Session) -> set[str]:
    """Retrieves the complete set of permission codes granted to the user."""
    permissions = set()
    for role in user.roles:
        # SUPER_ADMIN inherits all system permissions
        if role.name == "SUPER_ADMIN":
            all_perms = db.query(Permission.code).all()
            return {p[0] for p in all_perms}
        for perm in role.permissions:
            permissions.add(perm.code)
    return permissions


def require_permission(permission_code: str) -> Callable:
    """
    FastAPI dependency factory enforcing a required granular permission.
    Example: Depends(require_permission('documents.upload'))
    """
    def permission_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        user_perms = get_user_permissions(current_user, db)
        if permission_code not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: missing required permission '{permission_code}'."
            )
        return current_user

    return permission_checker


def require_role(role_name: str) -> Callable:
    """
    FastAPI dependency factory enforcing that the user has a specific role.
    Example: Depends(require_role('SUPER_ADMIN'))
    """
    def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        user_roles = {r.name for r in current_user.roles}
        if role_name not in user_roles and "SUPER_ADMIN" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: required role '{role_name}'."
            )
        return current_user

    return role_checker


def validate_document_access(
    document_id: str,
    user: User,
    db: Session,
    required_level: str = "READ"
) -> Document:
    """
    Validates resource-level document access to prevent cross-user ID tampering.
    Grants access if:
    1. User is SUPER_ADMIN or has 'documents.view_all' permission.
    2. User is the document's creator/uploader (doc.user_id == user.id or doc.uploaded_by == user.username).
    3. User has an explicit DocumentAccess grant matching required_level.
    4. User is an assigned reviewer on the document.
    """
    doc = db.query(Document).filter(Document.id == document_id, Document.is_deleted == False).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    user_perms = get_user_permissions(user, db)

    # 1. Administrative override
    if "documents.view_all" in user_perms or any(r.name == "SUPER_ADMIN" for r in user.roles):
        return doc

    # 2. Document creator / uploader
    if doc.user_id == user.id or doc.uploaded_by == user.username:
        return doc

    # 3. Explicit DocumentAccess entry
    access_grant = db.query(DocumentAccess).filter(
        DocumentAccess.document_id == document_id,
        DocumentAccess.user_id == user.id
    ).first()
    if access_grant:
        levels = ["READ", "REVIEW", "WRITE"]
        user_idx = levels.index(access_grant.access_level) if access_grant.access_level in levels else 0
        req_idx = levels.index(required_level) if required_level in levels else 0
        if user_idx >= req_idx:
            return doc

    # 4. Assigned Reviewer
    is_assigned = db.query(DocumentReview).filter(
        DocumentReview.document_id == document_id,
        DocumentReview.reviewer_user_id == user.id
    ).first()
    if is_assigned:
        return doc

    # Access denied
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not authorized to access or modify this document record."
    )
