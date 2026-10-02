"""
API Usage Monitor — tracks tokens, cost, and availability per provider.
This is provider-independent; add new providers by extending the cost map.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, date, timezone
from typing import Dict, Optional, Tuple
from enum import Enum

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.connection import get_db_context
from database.models import APIUsage, APIStatus, User

logger = structlog.get_logger(__name__)


class APIState(str, Enum):
    AVAILABLE = "AVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    API_UNAVAILABLE = "API_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"


# ─── Cost per 1K tokens (USD) ───────────────────────────────────────────
PROVIDER_COSTS: Dict[str, Dict[str, float]] = {
    "openai": {
        "gpt-4o": 0.005,
        "gpt-4o-mini": 0.00015,
        "gpt-4-turbo": 0.01,
        "gpt-3.5-turbo": 0.0005,
    },
    "gemini": {
        "gemini-1.5-flash": 0.000075,
        "gemini-1.5-pro": 0.00125,
    },
    "anthropic": {
        "claude-3-haiku-20240307": 0.00025,
        "claude-3-sonnet-20240229": 0.003,
    },
    "ollama": {},   # Local — no cost
}


def estimate_cost(provider: str, model: str, total_tokens: int) -> float:
    cost_per_k = PROVIDER_COSTS.get(provider, {}).get(model, 0.0)
    return (total_tokens / 1000) * cost_per_k


def get_role_limit_multiplier(role: str) -> float:
    return {
        "STUDENT": settings.STUDENT_LIMIT_MULTIPLIER,
        "FACULTY": settings.FACULTY_LIMIT_MULTIPLIER,
        "ADMIN": settings.ADMIN_LIMIT_MULTIPLIER,
    }.get(role, settings.STUDENT_LIMIT_MULTIPLIER)


class UsageMonitor:
    """
    Tracks usage against configured limits.
    Limits are INDEPENDENT of the provider's own quota system.
    """

    async def get_today_usage(
        self, db: AsyncSession, user_id: Optional[str] = None
    ) -> Dict:
        today = date.today()
        query = select(
            func.coalesce(func.sum(APIUsage.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(APIUsage.estimated_cost_usd), 0.0).label("cost"),
            func.count().label("requests"),
        ).where(
            func.date(APIUsage.created_at) == today,
            APIUsage.is_fallback == False,
        )
        if user_id:
            query = query.where(APIUsage.user_id == user_id)

        result = await db.execute(query)
        row = result.first()
        return {
            "tokens": int(row.tokens or 0),
            "cost_usd": float(row.cost or 0.0),
            "requests": int(row.requests or 0),
        }

    async def get_month_usage(
        self, db: AsyncSession, user_id: Optional[str] = None
    ) -> Dict:
        now = datetime.now(timezone.utc)
        query = select(
            func.coalesce(func.sum(APIUsage.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(APIUsage.estimated_cost_usd), 0.0).label("cost"),
            func.count().label("requests"),
        ).where(
            func.extract("year", APIUsage.created_at) == now.year,
            func.extract("month", APIUsage.created_at) == now.month,
            APIUsage.is_fallback == False,
        )
        if user_id:
            query = query.where(APIUsage.user_id == user_id)

        result = await db.execute(query)
        row = result.first()
        return {
            "tokens": int(row.tokens or 0),
            "cost_usd": float(row.cost or 0.0),
            "requests": int(row.requests or 0),
        }

    async def check_limits(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        user_role: str = "STUDENT",
    ) -> Tuple[bool, str]:
        """
        Returns (is_within_limit, reason).
        Checks both application-configured limits (not provider limits).
        """
        multiplier = get_role_limit_multiplier(user_role)
        daily_token_limit = int(settings.DAILY_TOKEN_LIMIT * multiplier)
        daily_cost_limit = settings.DAILY_COST_LIMIT_USD * multiplier
        monthly_token_limit = int(settings.MONTHLY_TOKEN_LIMIT * multiplier)
        monthly_cost_limit = settings.MONTHLY_COST_LIMIT_USD * multiplier

        today = await self.get_today_usage(db, user_id)
        month = await self.get_month_usage(db, user_id)

        if today["tokens"] >= daily_token_limit:
            return False, f"Daily token limit reached ({today['tokens']}/{daily_token_limit})"
        if today["cost_usd"] >= daily_cost_limit:
            return False, f"Daily cost limit reached (${today['cost_usd']:.4f}/${daily_cost_limit:.2f})"
        if month["tokens"] >= monthly_token_limit:
            return False, f"Monthly token limit reached"
        if month["cost_usd"] >= monthly_cost_limit:
            return False, f"Monthly cost limit reached"

        # Check fallback threshold (warn before hard limit)
        daily_pct = (today["tokens"] / max(daily_token_limit, 1)) * 100
        if daily_pct >= settings.FALLBACK_THRESHOLD_PERCENT:
            return False, f"Usage threshold reached ({daily_pct:.0f}% of daily limit)"

        return True, "OK"

    async def record_usage(
        self,
        db: AsyncSession,
        provider: str,
        model: str,
        request_tokens: int,
        response_tokens: int,
        status: str,
        user_id: Optional[str] = None,
        is_fallback: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        total = request_tokens + response_tokens
        cost = estimate_cost(provider, model, total)

        entry = APIUsage(
            user_id=user_id,
            provider=provider,
            model=model,
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            total_tokens=total,
            estimated_cost_usd=cost,
            status=status,
            is_fallback=is_fallback,
            error_message=error_message,
        )
        db.add(entry)
        await db.flush()

    async def get_summary(self, db: AsyncSession) -> Dict:
        today = await self.get_today_usage(db)
        month = await self.get_month_usage(db)
        return {
            "today": {
                **today,
                "token_limit": settings.DAILY_TOKEN_LIMIT,
                "cost_limit_usd": settings.DAILY_COST_LIMIT_USD,
                "usage_pct": min(
                    100,
                    (today["tokens"] / max(settings.DAILY_TOKEN_LIMIT, 1)) * 100,
                ),
            },
            "month": {
                **month,
                "token_limit": settings.MONTHLY_TOKEN_LIMIT,
                "cost_limit_usd": settings.MONTHLY_COST_LIMIT_USD,
                "usage_pct": min(
                    100,
                    (month["tokens"] / max(settings.MONTHLY_TOKEN_LIMIT, 1)) * 100,
                ),
            },
            "fallback_threshold_pct": settings.FALLBACK_THRESHOLD_PERCENT,
        }


# Singleton
usage_monitor = UsageMonitor()
