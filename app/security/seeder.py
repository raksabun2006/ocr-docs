from __future__ import annotations

"""
RBAC Database Seeder Module
Khmer Government Document Intelligence Platform

Idempotently seeds all initial permissions and standard roles:
- SUPER_ADMIN
- ADMIN
- OCR_OPERATOR
- REVIEWER
- VIEWER
"""

from typing import Dict, List, Tuple
from sqlalchemy.orm import Session
from app.models import Role, Permission, RolePermission

# Granular permissions defined by platform specifications
STANDARD_PERMISSIONS: List[Tuple[str, str, str]] = [
    # code, module, description
    ("users.view", "users", "View user accounts and profiles"),
    ("users.create", "users", "Create new user accounts"),
    ("users.update", "users", "Update user account information"),
    ("users.disable", "users", "Deactivate or disable user accounts"),
    ("users.delete", "users", "Permanently remove user accounts"),
    ("users.assign_role", "users", "Assign roles to user accounts"),

    ("roles.view", "roles", "View roles and assigned permissions"),
    ("roles.create", "roles", "Create new custom roles"),
    ("roles.update", "roles", "Update role details"),
    ("roles.delete", "roles", "Delete custom roles"),
    ("roles.assign_permission", "roles", "Grant or revoke permissions on roles"),

    ("documents.upload", "documents", "Upload documents for scanning"),
    ("documents.view", "documents", "View authorized documents"),
    ("documents.view_all", "documents", "View all system documents (Administrative override)"),
    ("documents.update", "documents", "Update document metadata and properties"),
    ("documents.delete", "documents", "Delete documents from system and archive"),
    ("documents.download", "documents", "Download original document binaries"),

    ("ocr.process", "ocr", "Trigger OCR processing on uploaded documents"),
    ("ocr.reprocess", "ocr", "Reprocess existing documents with different engines/settings"),
    ("ocr.view_results", "ocr", "View raw and structured OCR extractions"),
    ("ocr.manage_settings", "ocr", "Configure OCR engines and preprocessing strategies"),

    ("verification.view", "verification", "View documents in the verification desk"),
    ("verification.review", "verification", "Edit and correct extracted OCR fields"),
    ("verification.approve", "verification", "Approve and officially certify document records"),
    ("verification.reject", "verification", "Reject invalid or illegible document records"),

    ("audit.view", "audit", "View system and security audit logs"),
    ("audit.export", "audit", "Export audit trail logs for external compliance"),

    ("system.view", "system", "View system metrics, health, and configuration"),
    ("system.manage", "system", "Modify platform-level configuration parameters"),

    ("ai_models.view", "ai_models", "View available AI and Ollama OCR models"),
    ("ai_models.manage", "ai_models", "Configure and test AI model endpoints"),
]

# Role-to-permission mappings
ROLE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "SUPER_ADMIN": {
        "description": "Full platform administration with all permissions",
        "is_system": True,
        "permissions": "ALL"  # Special flag: receives every permission
    },
    "ADMIN": {
        "description": "Daily platform administrator without system-destructive privileges",
        "is_system": True,
        "permissions": [
            "users.view", "users.create", "users.update", "users.disable", "users.assign_role",
            "roles.view",
            "documents.upload", "documents.view", "documents.view_all", "documents.update", "documents.download",
            "ocr.process", "ocr.reprocess", "ocr.view_results",
            "verification.view", "verification.review", "verification.approve", "verification.reject",
            "audit.view",
            "system.view",
            "ai_models.view"
        ]
    },
    "OCR_OPERATOR": {
        "description": "Document ingestion and OCR processing officer",
        "is_system": True,
        "permissions": [
            "documents.upload", "documents.view", "documents.download",
            "ocr.process", "ocr.reprocess", "ocr.view_results",
            "verification.view"
        ]
    },
    "REVIEWER": {
        "description": "Civil registration reviewer authorized to correct and certify records",
        "is_system": True,
        "permissions": [
            "documents.view", "documents.download",
            "ocr.view_results",
            "verification.view", "verification.review", "verification.approve", "verification.reject"
        ]
    },
    "VIEWER": {
        "description": "Read-only access to authorized public records and OCR results",
        "is_system": True,
        "permissions": [
            "documents.view",
            "ocr.view_results"
        ]
    }
}


def seed_roles_and_permissions(db: Session) -> None:
    """
    Idempotently ensures all permissions, standard roles, and their mappings
    are seeded into the database. Safe to run on every startup or migration.
    """
    # 1. Seed Permissions
    permission_map: Dict[str, Permission] = {}
    existing_perms = {p.code: p for p in db.query(Permission).all()}

    for code, module, desc in STANDARD_PERMISSIONS:
        if code not in existing_perms:
            perm = Permission(code=code, module=module, description=desc)
            db.add(perm)
            db.flush()
            permission_map[code] = perm
        else:
            permission_map[code] = existing_perms[code]

    # 2. Seed Roles
    for role_name, role_info in ROLE_DEFINITIONS.items():
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(
                name=role_name,
                description=role_info["description"],
                is_system=role_info.get("is_system", True)
            )
            db.add(role)
            db.flush()

        # 3. Associate Permissions
        if role_info["permissions"] == "ALL":
            target_codes = [code for code, _, _ in STANDARD_PERMISSIONS]
        else:
            target_codes = role_info["permissions"]

        existing_role_perm_ids = {
            rp.permission_id for rp in db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
        }

        for p_code in target_codes:
            perm_obj = permission_map.get(p_code)
            if perm_obj and perm_obj.id not in existing_role_perm_ids:
                rp = RolePermission(role_id=role.id, permission_id=perm_obj.id)
                db.add(rp)

    db.commit()
