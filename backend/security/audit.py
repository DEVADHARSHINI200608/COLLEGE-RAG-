"""
Audit logging — write security-relevant events to the database.
"""
from __future__ import annotations

from typing import Optional, Any, Dict

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AuditLog

logger = structlog.get_logger(__name__)


async def log_event(
    db: AsyncSession,
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Persist an audit event. Non-blocking best-effort — errors are logged
    but do NOT raise exceptions that would abort the main request.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )
        db.add(entry)
        await db.flush()

        logger.info(
            "audit_event",
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    except Exception as exc:
        logger.error("audit_log_failed", error=str(exc), action=action)
