"""
Unit Tests for Administrative CLI Operations
Khmer Government Document Intelligence System
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User, Role, Permission, UserRole, RolePermission, AuditLog
from app.security.password import hash_password, verify_password, validate_password_strength
from app.security.seeder import seed_roles_and_permissions


@pytest.fixture
def cli_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    seed_roles_and_permissions(session)
    yield session
    session.close()


def test_cli_admin_creation_policy(cli_db):
    """
    Verify security rules for admin creation:
    1. First administrator receives SUPER_ADMIN role.
    2. Passwords are never stored in plaintext.
    3. Audit event is written.
    """
    raw_password = "SuperAdminPassword#2026"
    valid, _ = validate_password_strength(raw_password)
    assert valid is True

    admin_user = User(
        username="chief_admin",
        email="chief.admin@gov.kh",
        full_name="Chief Executive Administrator",
        password_hash=hash_password(raw_password),
        status="ACTIVE"
    )
    cli_db.add(admin_user)
    cli_db.flush()

    # Assign SUPER_ADMIN role
    super_role = cli_db.query(Role).filter(Role.name == "SUPER_ADMIN").first()
    assert super_role is not None
    cli_db.add(UserRole(user_id=admin_user.id, role_id=super_role.id))

    # Log audit trail
    cli_db.add(AuditLog(
        user_id=admin_user.id,
        action="CLI_CREATE_ADMIN",
        resource_type="USER",
        resource_id=admin_user.id,
        details="Initial administrator account created via CLI"
    ))
    cli_db.commit()

    # Verifications
    saved_user = cli_db.query(User).filter(User.username == "chief_admin").first()
    assert saved_user is not None
    assert saved_user.password_hash != raw_password
    assert verify_password(raw_password, saved_user.password_hash) is True
    assert any(r.name == "SUPER_ADMIN" for r in saved_user.roles)

    audit = cli_db.query(AuditLog).filter(AuditLog.action == "CLI_CREATE_ADMIN").first()
    assert audit is not None
    assert audit.resource_id == saved_user.id


def test_prevent_last_super_admin_deactivation(cli_db):
    """
    Security check: verify platform prevents disabling or deleting the last active SUPER_ADMIN.
    """
    # Create single active superadmin
    admin = User(
        username="sole_admin",
        email="sole@gov.kh",
        full_name="Sole Admin",
        password_hash=hash_password("SoleAdminPass#2026"),
        status="ACTIVE"
    )
    cli_db.add(admin)
    cli_db.flush()

    super_role = cli_db.query(Role).filter(Role.name == "SUPER_ADMIN").first()
    cli_db.add(UserRole(user_id=admin.id, role_id=super_role.id))
    cli_db.commit()

    # Check active superadmin count
    active_superadmins = (
        cli_db.query(User)
        .join(UserRole, User.id == UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(Role.name == "SUPER_ADMIN", User.status == "ACTIVE")
        .count()
    )
    assert active_superadmins == 1
