"""
Role-Based Access Control (RBAC) — define permissions per role.
Add new roles here without touching other files.
"""
from __future__ import annotations

from enum import Enum
from typing import Set, Dict

from fastapi import HTTPException, status


# ─── Roles ──────────────────────────────────────────────────────────────
class Role(str, Enum):
    STUDENT = "STUDENT"
    FACULTY = "FACULTY"
    ADMIN = "ADMIN"


# ─── Permissions ────────────────────────────────────────────────────────
class Permission(str, Enum):
    # Document permissions
    UPLOAD_OWN_MATERIAL = "UPLOAD_OWN_MATERIAL"
    UPLOAD_STANDARD_RESOURCE = "UPLOAD_STANDARD_RESOURCE"
    UPLOAD_CONFIDENTIAL = "UPLOAD_CONFIDENTIAL"
    DELETE_OWN_DOCUMENT = "DELETE_OWN_DOCUMENT"
    DELETE_ANY_DOCUMENT = "DELETE_ANY_DOCUMENT"

    # Access permissions
    ACCESS_STANDARD_RESOURCES = "ACCESS_STANDARD_RESOURCES"
    ACCESS_CONFIDENTIAL = "ACCESS_CONFIDENTIAL"
    ACCESS_OWN_MATERIALS = "ACCESS_OWN_MATERIALS"

    # RAG permissions
    USE_EDUCATIONAL_RAG = "USE_EDUCATIONAL_RAG"
    USE_CONFIDENTIAL_RAG = "USE_CONFIDENTIAL_RAG"
    USE_WEB_SEARCH = "USE_WEB_SEARCH"

    # Analysis permissions
    ANALYZE_STUDENT_RESPONSES = "ANALYZE_STUDENT_RESPONSES"
    COMPARE_STUDENT_LISTS = "COMPARE_STUDENT_LISTS"
    VIEW_MISSING_RESPONSES = "VIEW_MISSING_RESPONSES"
    SET_DEADLINES = "SET_DEADLINES"
    VIEW_REPORTS = "VIEW_REPORTS"

    # Admin permissions
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_ROLES = "MANAGE_ROLES"
    MANAGE_PERMISSIONS = "MANAGE_PERMISSIONS"
    MANAGE_SOURCES = "MANAGE_SOURCES"
    CONFIGURE_INTEGRATIONS = "CONFIGURE_INTEGRATIONS"
    MONITOR_API_USAGE = "MONITOR_API_USAGE"
    CONFIGURE_SYSTEM = "CONFIGURE_SYSTEM"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"


# ─── Role → Permissions mapping ─────────────────────────────────────────
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.STUDENT: {
        Permission.UPLOAD_OWN_MATERIAL,
        Permission.DELETE_OWN_DOCUMENT,
        Permission.ACCESS_STANDARD_RESOURCES,
        Permission.ACCESS_OWN_MATERIALS,
        Permission.USE_EDUCATIONAL_RAG,
        Permission.USE_WEB_SEARCH,
    },
    Role.FACULTY: {
        Permission.UPLOAD_OWN_MATERIAL,
        Permission.UPLOAD_STANDARD_RESOURCE,
        Permission.UPLOAD_CONFIDENTIAL,
        Permission.DELETE_OWN_DOCUMENT,
        Permission.ACCESS_STANDARD_RESOURCES,
        Permission.ACCESS_CONFIDENTIAL,
        Permission.ACCESS_OWN_MATERIALS,
        Permission.USE_EDUCATIONAL_RAG,
        Permission.USE_CONFIDENTIAL_RAG,
        Permission.USE_WEB_SEARCH,
        Permission.ANALYZE_STUDENT_RESPONSES,
        Permission.COMPARE_STUDENT_LISTS,
        Permission.VIEW_MISSING_RESPONSES,
        Permission.SET_DEADLINES,
        Permission.VIEW_REPORTS,
    },
    Role.ADMIN: {p for p in Permission},  # Admin has ALL permissions
}


def get_permissions(role: str) -> Set[Permission]:
    """Return the permission set for a given role string."""
    try:
        r = Role(role)
        return ROLE_PERMISSIONS.get(r, set())
    except ValueError:
        return set()


def has_permission(role: str, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in get_permissions(role)


def require_permission(role: str, permission: Permission) -> None:
    """Raise HTTP 403 if the role lacks the permission."""
    if not has_permission(role, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission.value} required.",
        )


def require_any_role(role: str, *allowed_roles: Role) -> None:
    """Raise HTTP 403 if the role is not in allowed_roles."""
    if role not in [r.value for r in allowed_roles]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' is not authorized for this action.",
        )
