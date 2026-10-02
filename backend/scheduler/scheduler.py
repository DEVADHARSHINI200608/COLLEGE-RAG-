"""
Background scheduler — deadline checks and API recovery.
Uses APScheduler. The LLM is never asked to remember deadlines.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import settings

logger = structlog.get_logger(__name__)

_scheduler = AsyncIOScheduler()


async def _check_deadlines():
    """Check for triggered deadlines and send notifications."""
    from database.connection import get_db_context
    from database.models import Deadline, DeadlineStatus, Notification, User
    from sqlalchemy import select

    logger.info("scheduler.checking_deadlines")
    now = datetime.now(timezone.utc)

    async with get_db_context() as db:
        result = await db.execute(
            select(Deadline).where(
                Deadline.status == DeadlineStatus.ACTIVE,
                Deadline.notification_sent == False,
            )
        )
        deadlines = result.scalars().all()

        for deadline in deadlines:
            # Combine date and time
            deadline_dt = datetime.combine(
                deadline.deadline_date,
                deadline.deadline_time,
                tzinfo=timezone.utc,
            )
            if now >= deadline_dt:
                await _trigger_deadline(db, deadline, now)

        await db.commit()


async def _trigger_deadline(db, deadline, now: datetime):
    """Create notifications for faculty/admin when deadline triggers."""
    from database.models import Notification, User, DeadlineStatus
    from sqlalchemy import select

    logger.info("scheduler.deadline_triggered", deadline_id=str(deadline.id))

    # Find faculty/admin users to notify
    result = await db.execute(
        select(User).where(User.role.in_(["FACULTY", "ADMIN"]), User.is_active == True)
    )
    recipients = result.scalars().all()

    for recipient in recipients:
        notification = Notification(
            deadline_id=str(deadline.id),
            recipient_id=str(recipient.id),
            title=f"Deadline Alert: {deadline.title}",
            message=(
                f"Reminder: {deadline.missing_count or 0} student(s) have not completed "
                f"the required form.\n\n"
                f"Deadline: {deadline.deadline_date} at {deadline.deadline_time}"
            ),
        )
        db.add(notification)

    # Mark deadline as triggered
    deadline.status = DeadlineStatus.TRIGGERED
    deadline.notification_sent = True

    logger.info("scheduler.notifications_created", count=len(recipients))


async def _check_external_api_recovery():
    """Periodic check: is the external LLM API available again?"""
    if not settings.AUTO_RECOVER_EXTERNAL_LLM:
        return

    from models.router import model_router, ModelMode
    if model_router.current_mode == ModelMode.LOCAL:
        available = await model_router.check_external_availability()
        if available:
            logger.info("scheduler.external_api_recovered")
            # The router will use external on next call automatically
            # Notification to admin can be added here


def start_scheduler():
    """Start background scheduler jobs."""
    if not settings.SCHEDULER_ENABLED:
        logger.info("scheduler.disabled")
        return

    _scheduler.add_job(
        _check_deadlines,
        trigger=IntervalTrigger(minutes=settings.DEADLINE_CHECK_INTERVAL_MINUTES),
        id="check_deadlines",
        replace_existing=True,
    )

    _scheduler.add_job(
        _check_external_api_recovery,
        trigger=IntervalTrigger(minutes=settings.RECOVERY_CHECK_INTERVAL_MINUTES),
        id="api_recovery_check",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("scheduler.started")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler.stopped")
