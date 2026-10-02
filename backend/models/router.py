"""
Model Router — centralized LLM routing.
This is the ONLY place that decides which model to use.
No other component should hard-code model selection.

Fallback flow (per requirement sections 19-24):
  1. Check application-level usage limits (UsageMonitor)
  2. Attempt external LLM call
  3. On API/quota failure → detect & return NEEDS_FALLBACK
  4. Frontend confirms → call with local model
"""
from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, RetryError
)

from config import settings
from monitoring.usage_tracker import usage_monitor, APIState

logger = structlog.get_logger(__name__)


class ModelMode(str, Enum):
    EXTERNAL = "EXTERNAL"
    LOCAL = "LOCAL"


class RouterResult(str, Enum):
    SUCCESS = "SUCCESS"
    NEEDS_FALLBACK = "NEEDS_FALLBACK"        # API failure → ask user
    USER_REJECTED_LOCAL = "USER_REJECTED"
    ERROR = "ERROR"


# ─── Exceptions that indicate API-level failures (trigger fallback) ──────
_API_FAILURE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)

_API_ERROR_CODES = {429, 503, 500, 502, 504}  # rate limit, unavailable, etc.


def _is_quota_error(exc: Exception) -> bool:
    """Detect quota/rate/budget errors from known providers."""
    msg = str(exc).lower()
    return any(k in msg for k in [
        "quota", "rate limit", "rate_limit", "exceeded",
        "insufficient_quota", "billing", "budget",
        "model_overloaded", "overloaded", "capacity",
        "too many requests", "429",
    ])


class ExternalLLMClient:
    """Thin wrapper around the configured external LLM provider."""

    def __init__(self):
        self.provider = settings.EXTERNAL_LLM_PROVIDER

    def _build_langchain_llm(self):
        if self.provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                timeout=60,
                max_retries=0,   # We handle retries via tenacity
            )
        elif self.provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GEMINI_API_KEY,
            )
        elif self.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=settings.ANTHROPIC_MODEL,
                api_key=settings.ANTHROPIC_API_KEY,
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def ainvoke(self, messages: List[Dict], **kwargs) -> Tuple[str, int, int]:
        """Returns (response_text, prompt_tokens, completion_tokens)."""
        llm = self._build_langchain_llm()
        from langchain_core.messages import HumanMessage, SystemMessage

        lc_messages = []
        for m in messages:
            if m["role"] == "system":
                lc_messages.append(SystemMessage(content=m["content"]))
            else:
                lc_messages.append(HumanMessage(content=m["content"]))

        response = await llm.ainvoke(lc_messages)
        # Extract usage if available
        usage = getattr(response, "usage_metadata", None) or {}
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        return response.content, prompt_tokens, completion_tokens


class LocalLLMClient:
    """Wrapper around Ollama or LlamaCPP local models."""

    def __init__(self):
        self.provider = settings.LOCAL_LLM_PROVIDER
        self.model = settings.OLLAMA_MODEL

    async def ainvoke(self, messages: List[Dict], **kwargs) -> Tuple[str, int, int]:
        """Returns (response_text, prompt_tokens, completion_tokens)."""
        if self.provider == "ollama":
            return await self._invoke_ollama(messages)
        raise ValueError(f"Unknown local provider: {self.provider}")

    async def _invoke_ollama(self, messages: List[Dict]) -> Tuple[str, int, int]:
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data.get("message", {}).get("content", "")
        prompt_eval = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)
        return content, prompt_eval, eval_count

    async def is_available(self) -> bool:
        """Check if the local model server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False


class ModelRouter:
    """
    Single point of control for LLM routing.
    All generation must go through this class.
    """

    def __init__(self):
        self.external = ExternalLLMClient()
        self.local = LocalLLMClient()
        self._current_mode: ModelMode = ModelMode.EXTERNAL

    @property
    def current_mode(self) -> ModelMode:
        return self._current_mode

    async def generate(
        self,
        messages: List[Dict],
        db=None,
        user_id: Optional[str] = None,
        user_role: str = "STUDENT",
        force_local: bool = False,
    ) -> Dict[str, Any]:
        """
        Main entry point.
        Returns:
          {
            "status": RouterResult,
            "content": str | None,
            "model_used": str,
            "is_local": bool,
            "needs_fallback_confirmation": bool,
            "fallback_reason": str | None,
          }
        """
        # ── Force local (after user confirmation) ─────────────────────
        if force_local:
            return await self._generate_local(messages, db, user_id)

        # ── Check application-level usage limits ──────────────────────
        if db:
            within_limit, reason = await usage_monitor.check_limits(
                db, user_id, user_role
            )
            if not within_limit:
                logger.warning("usage_limit_reached", reason=reason, user_id=user_id)
                return {
                    "status": RouterResult.NEEDS_FALLBACK,
                    "content": None,
                    "model_used": settings.EXTERNAL_LLM_PROVIDER,
                    "is_local": False,
                    "needs_fallback_confirmation": True,
                    "fallback_reason": reason,
                }

        # ── Attempt external LLM ───────────────────────────────────────
        try:
            content, p_tok, c_tok = await self._try_external(messages)
            self._current_mode = ModelMode.EXTERNAL
            if db:
                await usage_monitor.record_usage(
                    db=db,
                    provider=settings.EXTERNAL_LLM_PROVIDER,
                    model=self._get_model_name(),
                    request_tokens=p_tok,
                    response_tokens=c_tok,
                    status="SUCCESS",
                    user_id=user_id,
                    is_fallback=False,
                )
            return {
                "status": RouterResult.SUCCESS,
                "content": content,
                "model_used": f"{settings.EXTERNAL_LLM_PROVIDER}/{self._get_model_name()}",
                "is_local": False,
                "needs_fallback_confirmation": False,
                "fallback_reason": None,
            }

        except Exception as exc:
            # ── Classify the error ─────────────────────────────────────
            if _is_quota_error(exc) or isinstance(exc, _API_FAILURE_EXCEPTIONS):
                reason = f"External AI service error: {type(exc).__name__}"
                logger.warning("external_llm_failed_trigger_fallback", error=str(exc))
                if db:
                    await usage_monitor.record_usage(
                        db=db,
                        provider=settings.EXTERNAL_LLM_PROVIDER,
                        model=self._get_model_name(),
                        request_tokens=0, response_tokens=0,
                        status="API_UNAVAILABLE",
                        user_id=user_id,
                        is_fallback=False,
                        error_message=str(exc),
                    )
                return {
                    "status": RouterResult.NEEDS_FALLBACK,
                    "content": None,
                    "model_used": settings.EXTERNAL_LLM_PROVIDER,
                    "is_local": False,
                    "needs_fallback_confirmation": True,
                    "fallback_reason": reason,
                }
            # Non-API errors (e.g. bad prompt format) → propagate
            logger.error("external_llm_unexpected_error", error=str(exc))
            raise

    async def _try_external(self, messages: List[Dict]) -> Tuple[str, int, int]:
        return await self.external.ainvoke(messages)

    async def _generate_local(
        self, messages: List[Dict], db=None, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not settings.LOCAL_LLM_ENABLED:
            return {
                "status": RouterResult.ERROR,
                "content": None,
                "model_used": "local",
                "is_local": True,
                "needs_fallback_confirmation": False,
                "fallback_reason": "Local model is not enabled.",
            }
        try:
            content, p_tok, c_tok = await self.local.ainvoke(messages)
            self._current_mode = ModelMode.LOCAL
            if db:
                await usage_monitor.record_usage(
                    db=db,
                    provider=settings.LOCAL_LLM_PROVIDER,
                    model=settings.OLLAMA_MODEL,
                    request_tokens=p_tok, response_tokens=c_tok,
                    status="LOCAL_FALLBACK",
                    user_id=user_id,
                    is_fallback=True,
                )
            return {
                "status": RouterResult.SUCCESS,
                "content": content,
                "model_used": f"local/{settings.OLLAMA_MODEL}",
                "is_local": True,
                "needs_fallback_confirmation": False,
                "fallback_reason": None,
            }
        except Exception as exc:
            logger.error("local_llm_failed", error=str(exc))
            return {
                "status": RouterResult.ERROR,
                "content": None,
                "model_used": "local",
                "is_local": True,
                "needs_fallback_confirmation": False,
                "fallback_reason": f"Local model error: {str(exc)}",
            }

    def _get_model_name(self) -> str:
        return {
            "openai": settings.OPENAI_MODEL,
            "gemini": settings.GEMINI_MODEL,
            "anthropic": settings.ANTHROPIC_MODEL,
        }.get(settings.EXTERNAL_LLM_PROVIDER, "unknown")

    async def check_external_availability(self) -> bool:
        """Used by the recovery scheduler."""
        try:
            test_msg = [{"role": "user", "content": "ping"}]
            await self.external.ainvoke(test_msg)
            return True
        except Exception:
            return False

    async def check_local_availability(self) -> bool:
        return await self.local.is_available()


# Singleton
model_router = ModelRouter()
