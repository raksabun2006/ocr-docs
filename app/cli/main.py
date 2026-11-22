from __future__ import annotations

"""
Command-Line Administrative Interface (CLI)
Khmer Government Document Intelligence Platform

Usage:
    python -m app.cli create-admin
    python -m app.cli list-users
    python -m app.cli create-user
    python -m app.cli reset-password
    python -m app.cli assign-role
    python -m app.cli list-roles
    python -m app.cli list-permissions
    python -m app.cli create-role
    python -m app.cli grant-permission
    python -m app.cli revoke-permission
    python -m app.cli system-info
"""

import sys
import getpass
import argparse
from typing import Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import (
    User, Role, Permission, UserRole, RolePermission, AuditLog, Document
)
from app.security.password import (
    validate_password_strength, hash_password
)
from app.security.seeder import seed_roles_and_permissions
from app.services.ocr_service import ocr_service
from app.config import settings


def get_db_session() -> Session:
    """Initializes schema and returns an active database session."""
    init_db()
    db = SessionLocal()
    seed_roles_and_permissions(db)
    return db


def log_cli_audit(db: Session, action: str, resource_type: str, resource_id: str, details: dict):
    """Writes an immutable audit log entry for administrative CLI operations."""
    audit_entry = AuditLog(
        user_id="SYSTEM_CLI",
        action=action.upper(),
        resource_type=resource_type.upper(),
        resource_id=resource_id,
        ip_address="127.0.0.1",
        outcome="SUCCESS",
        details=details
    )
    db.add(audit_entry)
    db.commit()


# ==============================================================================
# CLI Commands
# ==============================================================================

def cmd_create_admin(args):
    """
    Interactive command to create the initial SUPER_ADMIN.
    Enforces strict security guidelines:
    - Never prints password.
    - Masks input.
    - Validates strength and uniqueness.
    - Writes audit record.
    """
    db = get_db_session()
    print("=" * 70)
    print(" KHMER GOVERNMENT DOCUMENT INTELLIGENCE PLATFORM")
    print(" Initial Administrator Provisioning (CLI)")
    print("=" * 70)

    try:
        # Check if an active SUPER_ADMIN already exists
        super_admin_role = db.query(Role).filter(Role.name == "SUPER_ADMIN").first()
        existing_super_admins = []
        if super_admin_role:
            existing_super_admins = db.query(User).join(User.roles).filter(
                Role.name == "SUPER_ADMIN",
                User.status == "ACTIVE"
            ).all()

        if existing_super_admins:
            print(f"\n[NOTE] Found {len(existing_super_admins)} existing active SUPER_ADMIN account(s).")
            confirm = input("Do you wish to provision an additional SUPER_ADMIN account? (yes/no): ").strip().lower()
            if confirm not in ("yes", "y"):
                print("Operation aborted by operator.")
                return

        # 1. Username
        while True:
            username = input("\n1. Enter administrator username: ").strip()
            if not username or len(username) < 3:
                print("Error: Username must be at least 3 characters long.")
                continue
            if db.query(User).filter(User.username == username).first():
                print(f"Error: Username '{username}' already exists. Choose another.")
                continue
            break

        # 2. Email
        while True:
            email = input("2. Enter administrator email: ").strip()
            if "@" not in email or "." not in email:
                print("Error: Invalid email format.")
                continue
            if db.query(User).filter(User.email == email).first():
                print(f"Error: Email '{email}' is already registered.")
                continue
            break

        # 3. Full Name
        while True:
            full_name = input("3. Enter full name: ").strip()
            if not full_name:
                print("Error: Full name cannot be empty.")
                continue
            break

        # 4 & 5. Password & Confirmation (Masked)
        while True:
            pwd = getpass.getpass("4. Enter password: ")
            is_valid, err_msg = validate_password_strength(pwd, min_length=10)
            if not is_valid:
                print(f"Error: {err_msg}")
                continue

            pwd_confirm = getpass.getpass("5. Confirm password: ")
            if pwd != pwd_confirm:
                print("Error: Passwords do not match. Please try again.")
                continue
            break

        # 6. Create User Account
        pwd_hash = hash_password(pwd)
        admin_user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=pwd_hash,
            status="ACTIVE"
        )
        db.add(admin_user)
        db.flush()

        # 7. Assign SUPER_ADMIN role
        if super_admin_role:
            user_role = UserRole(user_id=admin_user.id, role_id=super_admin_role.id, assigned_by="CLI_INITIAL_SETUP")
            db.add(user_role)

        db.commit()

        # 8. Audit Log
        log_cli_audit(
            db,
            action="CREATE_SUPER_ADMIN",
            resource_type="USER",
            resource_id=admin_user.id,
            details={"username": username, "email": email}
        )

        print("\n" + "=" * 70)
        print("✓ SUCCESS: Administrator account created successfully!")
        print(f"  User ID:   {admin_user.id}")
        print(f"  Username:  {username}")
        print(f"  Email:     {email}")
        print(f"  Role:      SUPER_ADMIN")
        print("=" * 70)

    except Exception as exc:
        db.rollback()
        print(f"\n[FATAL ERROR] Failed to create administrator: {exc}")
    finally:
        db.close()


def cmd_list_users(args):
    """Lists all user accounts in the platform."""
    db = get_db_session()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        print("\n" + "=" * 80)
        print(f"{'USERNAME':<20} {'FULL NAME':<22} {'STATUS':<10} {'ROLES':<20}")
        print("=" * 80)
        for u in users:
            role_names = ", ".join([r.name for r in u.roles]) or "None"
            print(f"{u.username:<20} {u.full_name[:20]:<22} {u.status:<10} {role_names:<20}")
        print("=" * 80)
        print(f"Total Users: {len(users)}\n")
    finally:
        db.close()


def cmd_create_user(args):
    """Interactively creates a standard user."""
    db = get_db_session()
    try:
        username = input("Enter username: ").strip()
        if db.query(User).filter(User.username == username).first():
            print(f"Error: Username '{username}' already exists.")
            return

        email = input("Enter email: ").strip()
        if db.query(User).filter(User.email == email).first():
            print(f"Error: Email '{email}' already registered.")
            return

        full_name = input("Enter full name: ").strip()
        pwd = getpass.getpass("Enter password: ")
        is_valid, err_msg = validate_password_strength(pwd, min_length=8)
        if not is_valid:
            print(f"Error: {err_msg}")
            return

        pwd_confirm = getpass.getpass("Confirm password: ")
        if pwd != pwd_confirm:
            print("Error: Passwords do not match.")
            return

        # Choose role
        roles = db.query(Role).all()
        print("\nAvailable Roles:")
        for idx, r in enumerate(roles, 1):
            print(f"  [{idx}] {r.name} - {r.description}")
        choice = input("Select role number [default 5: VIEWER]: ").strip()
        try:
            chosen_role = roles[int(choice) - 1] if choice else db.query(Role).filter(Role.name == "VIEWER").first()
        except (ValueError, IndexError):
            chosen_role = db.query(Role).filter(Role.name == "VIEWER").first()

        new_user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hash_password(pwd),
            status="ACTIVE"
        )
        db.add(new_user)
        db.flush()

        if chosen_role:
            db.add(UserRole(user_id=new_user.id, role_id=chosen_role.id, assigned_by="CLI"))

        db.commit()
        log_cli_audit(db, "CREATE_USER", "USER", new_user.id, {"username": username, "role": chosen_role.name if chosen_role else None})
        print(f"\n✓ User '{username}' created with role '{chosen_role.name if chosen_role else 'None'}'.")
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
    finally:
        db.close()


def cmd_reset_password(args):
    """Resets a user's password securely."""
    db = get_db_session()
    try:
        username = input("Enter username to reset password: ").strip()
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"Error: User '{username}' not found.")
            return

        new_pwd = getpass.getpass("Enter new password: ")
        is_valid, err = validate_password_strength(new_pwd, min_length=8)
        if not is_valid:
            print(f"Error: {err}")
            return

        confirm = getpass.getpass("Confirm new password: ")
        if new_pwd != confirm:
            print("Error: Passwords do not match.")
            return

        user.password_hash = hash_password(new_pwd)
        user.failed_login_attempts = 0
        if user.status == "LOCKED":
            user.status = "ACTIVE"
        db.commit()

        log_cli_audit(db, "RESET_PASSWORD", "USER", user.id, {"username": username})
        print(f"✓ Password for user '{username}' reset successfully.")
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
    finally:
        db.close()


def cmd_assign_role(args):
    """Assigns an approved role to a user."""
    db = get_db_session()
    try:
        username = args.username or input("Enter username: ").strip()
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"Error: User '{username}' not found.")
            return

        role_name = args.role or input("Enter role name (SUPER_ADMIN, ADMIN, OCR_OPERATOR, REVIEWER, VIEWER): ").strip().upper()
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            print(f"Error: Role '{role_name}' does not exist.")
            return

        existing = db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.role_id == role.id).first()
        if existing:
            print(f"Notice: User '{username}' already has role '{role_name}'.")
            return

        db.add(UserRole(user_id=user.id, role_id=role.id, assigned_by="CLI"))
        db.commit()
        log_cli_audit(db, "ASSIGN_ROLE", "USER", user.id, {"username": username, "role": role_name})
        print(f"✓ Role '{role_name}' assigned to '{username}'.")
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
    finally:
        db.close()


def cmd_list_roles(args):
    """Lists all configured roles."""
    db = get_db_session()
    try:
        roles = db.query(Role).all()
        print("\n" + "=" * 70)
        print(f"{'ROLE NAME':<20} {'PERMISSIONS COUNT':<20} {'DESCRIPTION'}")
        print("=" * 70)
        for r in roles:
            p_count = len(r.permissions)
            print(f"{r.name:<20} {p_count:<20} {r.description or ''}")
        print("=" * 70 + "\n")
    finally:
        db.close()


def cmd_list_permissions(args):
    """Lists all system permissions grouped by module."""
    db = get_db_session()
    try:
        perms = db.query(Permission).order_by(Permission.module, Permission.code).all()
        print("\n" + "=" * 80)
        print(f"{'PERMISSION CODE':<30} {'MODULE':<15} {'DESCRIPTION'}")
        print("=" * 80)
        for p in perms:
            print(f"{p.code:<30} {p.module:<15} {p.description or ''}")
        print("=" * 80)
        print(f"Total Permissions: {len(perms)}\n")
    finally:
        db.close()


def cmd_create_role(args):
    """Creates a custom role."""
    db = get_db_session()
    try:
        name = args.name or input("Enter new role name: ").strip().upper()
        if db.query(Role).filter(Role.name == name).first():
            print(f"Error: Role '{name}' already exists.")
            return

        desc = args.description or input("Enter description: ").strip()
        role = Role(name=name, description=desc, is_system=False)
        db.add(role)
        db.commit()
        log_cli_audit(db, "CREATE_ROLE", "ROLE", str(role.id), {"name": name})
        print(f"✓ Custom role '{name}' created.")
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
    finally:
        db.close()


def cmd_grant_permission(args):
    """Grants a permission to a role."""
    db = get_db_session()
    try:
        role_name = args.role or input("Enter role name: ").strip().upper()
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            print(f"Error: Role '{role_name}' not found.")
            return

        perm_code = args.permission or input("Enter permission code (e.g., 'documents.upload'): ").strip()
        perm = db.query(Permission).filter(Permission.code == perm_code).first()
        if not perm:
            print(f"Error: Permission '{perm_code}' does not exist.")
            return

        existing = db.query(RolePermission).filter(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == perm.id
        ).first()
        if existing:
            print(f"Notice: Role '{role_name}' already possesses '{perm_code}'.")
            return

        db.add(RolePermission(role_id=role.id, permission_id=perm.id))
        db.commit()
        log_cli_audit(db, "GRANT_PERMISSION", "ROLE", str(role.id), {"role": role_name, "permission": perm_code})
        print(f"✓ Permission '{perm_code}' granted to '{role_name}'.")
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
    finally:
        db.close()


def cmd_revoke_permission(args):
    """Revokes a permission from a role."""
    db = get_db_session()
    try:
        role_name = args.role or input("Enter role name: ").strip().upper()
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            print(f"Error: Role '{role_name}' not found.")
            return

        # Safeguard: Do not modify system SUPER_ADMIN permissions
        if role.name == "SUPER_ADMIN":
            print("Error: Permissions cannot be revoked from SUPER_ADMIN system role.")
            return

        perm_code = args.permission or input("Enter permission code to revoke: ").strip()
        perm = db.query(Permission).filter(Permission.code == perm_code).first()
        if not perm:
            print(f"Error: Permission '{perm_code}' does not exist.")
            return

        existing = db.query(RolePermission).filter(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == perm.id
        ).first()
        if not existing:
            print(f"Notice: Role '{role_name}' does not have '{perm_code}'.")
            return

        db.delete(existing)
        db.commit()
        log_cli_audit(db, "REVOKE_PERMISSION", "ROLE", str(role.id), {"role": role_name, "permission": perm_code})
        print(f"✓ Permission '{perm_code}' revoked from '{role_name}'.")
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
    finally:
        db.close()


def cmd_system_info(args):
    """Displays platform health and configuration summary safely."""
    db = get_db_session()
    try:
        ocr_env = ocr_service.verify_environment()
        user_count = db.query(User).count()
        doc_count = db.query(Document).filter(Document.is_deleted == False).count()
        audit_count = db.query(AuditLog).count()

        print("\n" + "=" * 70)
        print(" KHMER GOVERNMENT DOCUMENT INTELLIGENCE PLATFORM — SYSTEM INFO")
        print("=" * 70)
        print(f" Application Name:    {settings.APP_NAME}")
        print(f" Environment:         {settings.APP_ENV}")
        print(f" Database Driver:     {db.bind.dialect.name.upper()}")
        print(f" Registered Users:    {user_count}")
        print(f" Total Documents:     {doc_count}")
        print(f" Audit Log Entries:   {audit_count}")
        print("-" * 70)
        print(" OCR Subsystem:")
        print(f"   - Tesseract Binary:  {'✓ READY' if ocr_env['tesseract_installed'] else '✗ NOT FOUND'}")
        print(f"   - Languages Loaded:  {', '.join(ocr_env['languages_found']) if ocr_env['languages_found'] else 'None'}")
        print(f"   - English Support:   {'✓ YES' if ocr_env['has_english'] else '✗ MISSING'}")
        print(f"   - Khmer Support:     {'✓ YES' if ocr_env['has_khmer'] else '✗ MISSING'}")
        print("=" * 70 + "\n")
    finally:
        db.close()


# ==============================================================================
# CLI Entrypoint
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Khmer Government Document Intelligence System - Administrative CLI",
        prog="python -m app.cli"
    )
    subparsers = parser.add_subparsers(dest="command", help="Administrative Command")

    # create-admin
    subparsers.add_parser("create-admin", help="Provision the initial SUPER_ADMIN account interactively")

    # list-users
    subparsers.add_parser("list-users", help="List all platform user accounts")

    # create-user
    subparsers.add_parser("create-user", help="Create a new user account interactively")

    # reset-password
    subparsers.add_parser("reset-password", help="Reset a user password securely")

    # assign-role
    p_assign = subparsers.add_parser("assign-role", help="Assign a role to a user")
    p_assign.add_argument("--username", type=str, help="Target username")
    p_assign.add_argument("--role", type=str, help="Role name")

    # list-roles
    subparsers.add_parser("list-roles", help="List all configured roles")

    # list-permissions
    subparsers.add_parser("list-permissions", help="List all granular permissions")

    # create-role
    p_crole = subparsers.add_parser("create-role", help="Create a custom role")
    p_crole.add_argument("--name", type=str, help="Role name")
    p_crole.add_argument("--description", type=str, help="Role description")

    # grant-permission
    p_grant = subparsers.add_parser("grant-permission", help="Grant permission to a role")
    p_grant.add_argument("--role", type=str, help="Role name")
    p_grant.add_argument("--permission", type=str, help="Permission code")

    # revoke-permission
    p_revoke = subparsers.add_parser("revoke-permission", help="Revoke permission from a role")
    p_revoke.add_argument("--role", type=str, help="Role name")
    p_revoke.add_argument("--permission", type=str, help="Permission code")

    # system-info
    subparsers.add_parser("system-info", help="Display platform and OCR status")

    args = parser.parse_args()

    commands = {
        "create-admin": cmd_create_admin,
        "list-users": cmd_list_users,
        "create-user": cmd_create_user,
        "reset-password": cmd_reset_password,
        "assign-role": cmd_assign_role,
        "list-roles": cmd_list_roles,
        "list-permissions": cmd_list_permissions,
        "create-role": cmd_create_role,
        "grant-permission": cmd_grant_permission,
        "revoke-permission": cmd_revoke_permission,
        "system-info": cmd_system_info,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
