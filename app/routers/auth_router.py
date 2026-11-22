"""
Authentication & Authorization API Router
Khmer Government Document Intelligence System

Implements secure login, password change, token refresh/logout with JTI revocation,
account lockout policies, and current session inspection.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, Role, Permission, TokenRevocation, AuditLog
from app.security.password import verify_password, hash_password, validate_password_strength
from app.security.tokens import create_access_token, decode_access_token
from app.security.dependencies import get_current_user, get_token_from_header

router = APIRouter(prefix="/auth", tags=["Authentication & Session"])


# ------------------------------------------------------------------------------
# Request / Response Schemas
# ------------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="Account password")


class UserProfileResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    status: str
    roles: List[str]
    permissions: List[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserProfileResponse


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


# ------------------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate user, check account lockout status, verify credentials,
    and issue a cryptographically signed JWT bearer token.
    """
    login_id = req.username.strip()
    user = db.query(User).filter(
        (User.username == login_id) | (User.email == login_id)
    ).first()

    client_ip = request.client.host if request.client else "unknown"

    if not user or user.is_deleted:
        # Prevent user enumeration with constant-time dummy verification
        verify_password("dummy_password", "$scrypt$ln=14,r=8,p=1$dummy$dummy")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    now = datetime.now(timezone.utc)

    # 1. Check Account Lockout
    if user.status == "LOCKED":
        if user.locked_until and user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is temporarily locked due to failed attempts. Try again in {remaining} minute(s)."
            )
        else:
            # Lockout expired, restore to ACTIVE
            user.status = "ACTIVE"
            user.failed_login_attempts = 0
            user.locked_until = None

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status.lower()}. Please contact a system administrator."
        )

    # 2. Verify Password
    if not verify_password(req.password, user.password_hash):
        user.failed_login_attempts += 1
        audit_action = "AUTH_LOGIN_FAILED"

        if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            user.status = "LOCKED"
            user.locked_until = now + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
            audit_action = "AUTH_ACCOUNT_LOCKED"

        db.add(AuditLog(
            user_id=user.id,
            action=audit_action,
            resource_type="USER",
            resource_id=user.id,
            ip_address=client_ip,
            details=f"Failed login attempt {user.failed_login_attempts}/{settings.MAX_FAILED_LOGIN_ATTEMPTS}"
        ))
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # 3. Successful Login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    role_names = [r.name for r in user.roles]
    permissions_set = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions_set.add(perm.code)
    permission_names = sorted(list(permissions_set))

    # Issue JWT Token
    import uuid
    token_jti = str(uuid.uuid4())
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={
            "sub": user.id,
            "username": user.username,
            "roles": role_names,
            "permissions": permission_names,
            "jti": token_jti,
        },
        expires_delta_seconds=int(expires_delta.total_seconds())
    )

    db.add(AuditLog(
        user_id=user.id,
        action="AUTH_LOGIN_SUCCESS",
        resource_type="USER",
        resource_id=user.id,
        ip_address=client_ip,
        details=f"User {user.username} successfully logged in"
    ))
    db.commit()

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserProfileResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            status=user.status,
            roles=role_names,
            permissions=permission_names,
        )
    )


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revokes the current JWT bearer token by recording its JTI in token_revocations.
    """
    token = get_token_from_header(request)
    client_ip = request.client.host if request.client else "unknown"

    if token:
        payload = decode_access_token(token)
        if payload and "jti" in payload:
            jti = payload["jti"]
            exp = payload.get("exp")
            exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc) + timedelta(hours=2)

            revocation = TokenRevocation(
                jti=jti,
                user_id=current_user.id,
                expires_at=exp_dt
            )
            db.add(revocation)

    db.add(AuditLog(
        user_id=current_user.id,
        action="AUTH_LOGOUT",
        resource_type="SESSION",
        resource_id=current_user.id,
        ip_address=client_ip,
        details=f"User {current_user.username} logged out"
    ))
    db.commit()

    return {"success": True, "message": "Successfully logged out"}


@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Returns the authenticated user profile along with active roles and permissions."""
    role_names = [r.name for r in current_user.roles]
    permissions_set = set()
    for role in current_user.roles:
        for perm in role.permissions:
            permissions_set.add(perm.code)

    return UserProfileResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        status=current_user.status,
        roles=role_names,
        permissions=sorted(list(permissions_set))
    )


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates password for the currently authenticated user."""
    client_ip = request.client.host if request.client else "unknown"

    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password does not match"
        )

    if req.new_password != req.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation do not match"
        )

    is_valid, reason = validate_password_strength(req.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason
        )

    current_user.password_hash = hash_password(req.new_password)
    current_user.updated_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        user_id=current_user.id,
        action="AUTH_PASSWORD_CHANGED",
        resource_type="USER",
        resource_id=current_user.id,
        ip_address=client_ip,
        details=f"User {current_user.username} changed account password"
    ))
    db.commit()

    return {"success": True, "message": "Password changed successfully"}
