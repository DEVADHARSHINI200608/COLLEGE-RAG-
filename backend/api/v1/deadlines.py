"""
Deadline management routes — calendar, scheduler, notifications.
"""
from __future__ import annotations

from datetime import date, time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.rbac import Permission, require_permission
from database.connection import get_db
from database.models import Deadline, DeadlineStatus, Notification, User

router = APIRouter(prefix="/deadlines", tags=["deadlines"])


class DeadlineCreate(BaseModel):
    title: str
    description: Optional[str] = None
    deadline_date: date
    deadline_time: time
    timezone: str = "Asia/Kolkata"
    target_group: Optional[str] = None
    master_list_source_id: Optional[str] = None
    response_source_id: Optional[str] = None
    missing_count: Optional[int] = None
    missing_names: List[str] = []


class DeadlineResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    deadline_date: str
    deadline_time: str
    timezone: str
    status: str
    missing_count: Optional[int]
    missing_names: List[str]
    created_at: str


@router.post("/", response_model=DeadlineResponse, status_code=status.HTTP_201_CREATED)
async def create_deadline(
    body: DeadlineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(current_user.role, Permission.SET_DEADLINES)

    deadline = Deadline(
        title=body.title,
        description=body.description,
        deadline_date=body.deadline_date,
        deadline_time=body.deadline_time,
        timezone=body.timezone,
        created_by=str(current_user.id),
        target_group=body.target_group,
        master_list_source_id=body.master_list_source_id,
        response_source_id=body.response_source_id,
        missing_count=body.missing_count,
        missing_names=body.missing_names,
    )
    db.add(deadline)
    await db.flush()
    await db.refresh(deadline)

    return DeadlineResponse(
        id=str(deadline.id),
        title=deadline.title,
        description=deadline.description,
        deadline_date=str(deadline.deadline_date),
        deadline_time=str(deadline.deadline_time),
        timezone=deadline.timezone,
        status=deadline.status,
        missing_count=deadline.missing_count,
        missing_names=deadline.missing_names or [],
        created_at=deadline.created_at.isoformat(),
    )


@router.get("/", response_model=List[DeadlineResponse])
async def list_deadlines(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(current_user.role, Permission.SET_DEADLINES)

    result = await db.execute(
        select(Deadline)
        .where(Deadline.status != DeadlineStatus.CANCELLED)
        .order_by(Deadline.deadline_date)
    )
    deadlines = result.scalars().all()

    return [
        DeadlineResponse(
            id=str(d.id),
            title=d.title,
            description=d.description,
            deadline_date=str(d.deadline_date),
            deadline_time=str(d.deadline_time),
            timezone=d.timezone,
            status=d.status,
            missing_count=d.missing_count,
            missing_names=d.missing_names or [],
            created_at=d.created_at.isoformat(),
        )
        for d in deadlines
    ]


@router.get("/notifications")
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.recipient_id == str(current_user.id))
        .order_by(Notification.sent_at.desc())
        .limit(50)
    )
    notifications = result.scalars().all()

    return [
        {
            "id": str(n.id),
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "sent_at": n.sent_at.isoformat(),
        }
        for n in notifications
    ]


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == str(current_user.id),
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(404, "Notification not found.")

    notification.is_read = True
    return {"status": "marked_read"}
