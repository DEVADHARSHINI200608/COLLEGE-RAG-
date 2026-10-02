"""
Admin routes — user management, API usage dashboard, system settings.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.rbac import Permission, require_permission
from database.connection import get_db
from database.models import User, APIUsage, AuditLog, UserRole
from monitoring.usage_tracker import usage_monitor

router = APIRouter(prefix="/admin", tags=["admin"])


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    department: Optional[str] = None


# ─── User Management ────────────────────────────────────────────────────
@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(current_user.role, Permission.MANAGE_USERS)
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "department": u.department,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(current_user.role, Permission.MANAGE_USERS)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found.")

    if body.role:
        if body.role not in [r.value for r in UserRole]:
            raise HTTPException(400, f"Invalid role: {body.role}")
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.department is not None:
        user.department = body.department

    return {"status": "updated", "user_id": user_id}


# ─── API Usage Dashboard ─────────────────────────────────────────────────
@router.get("/api-usage/summary")
async def api_usage_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(current_user.role, Permission.MONITOR_API_USAGE)
    summary = await usage_monitor.get_summary(db)

    from models.router import model_router, ModelMode
    local_available = await model_router.check_local_availability()

    return {
        **summary,
        "current_model_mode": model_router.current_mode.value,
        "is_using_local": model_router.current_mode == ModelMode.LOCAL,
        "local_model_available": local_available,
        "external_provider": __import__("config").settings.EXTERNAL_LLM_PROVIDER,
    }


@router.get("/api-usage/recent")
async def recent_api_usage(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(current_user.role, Permission.MONITOR_API_USAGE)
    result = await db.execute(
        select(APIUsage).order_by(APIUsage.created_at.desc()).limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "provider": r.provider,
            "model": r.model,
            "total_tokens": r.total_tokens,
            "estimated_cost_usd": r.estimated_cost_usd,
            "status": r.status,
            "is_fallback": r.is_fallback,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


# ─── Audit Logs ──────────────────────────────────────────────────────────
@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(current_user.role, Permission.VIEW_AUDIT_LOGS)
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(l.id),
            "user_id": str(l.user_id) if l.user_id else None,
            "action": l.action,
            "resource_type": l.resource_type,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
