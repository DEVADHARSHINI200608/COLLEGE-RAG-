"""
FastAPI dependencies — current user extraction and authorization.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_handler import verify_access_token
from auth.rbac import Permission, require_permission
from database.connection import get_db
from database.models import User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the current user from JWT.
    Checks Authorization header first, then httpOnly cookie.
    """
    token: Optional[str] = None

    # 1. Authorization header (Bearer token)
    if credentials:
        token = credentials.credentials

    # 2. httpOnly cookie fallback
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


def require_role_permission(permission: Permission):
    """Factory: returns a FastAPI dependency that checks a specific permission."""
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        require_permission(current_user.role, permission)
        return current_user
    return checker


# ─── Convenience shorthands ─────────────────────────────────────────────
RequireStudent = Depends(get_current_user)
RequireFaculty = Depends(require_role_permission(Permission.UPLOAD_CONFIDENTIAL))
RequireAdmin = Depends(require_role_permission(Permission.MANAGE_USERS))
