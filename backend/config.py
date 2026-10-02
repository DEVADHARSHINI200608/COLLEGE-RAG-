"""
Central configuration — all settings loaded from environment variables.
Never hard-code secrets here.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal, List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Application ────────────────────────────────────────
    APP_NAME: str = "Agentic RAG Platform"
    APP_ENV: Literal["development", "production"] = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION-AT-LEAST-32-CHARS"

    # ─── Database ───────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./rag_platform.db"

    # ─── Vector DB ──────────────────────────────────────────
    VECTOR_DB_TYPE: Literal["chroma", "weaviate"] = "chroma"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_API_KEY: str = ""

    # ─── File Storage ───────────────────────────────────────
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    FILE_UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50

    # ─── JWT ────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─── External LLM ───────────────────────────────────────
    EXTERNAL_LLM_PROVIDER: Literal[
        "openai", "gemini", "anthropic", "azure_openai"
    ] = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = ""

    # ─── Embedding Model ────────────────────────────────────
    EMBEDDING_PROVIDER: Literal[
        "openai", "sentence_transformers", "local"
    ] = "sentence_transformers"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ─── Local LLM ──────────────────────────────────────────
    LOCAL_LLM_PROVIDER: Literal["ollama", "llamacpp"] = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    LOCAL_LLM_ENABLED: bool = True

    # ─── API Usage Limits ───────────────────────────────────
    DAILY_TOKEN_LIMIT: int = 100_000
    MONTHLY_TOKEN_LIMIT: int = 2_000_000
    DAILY_COST_LIMIT_USD: float = 5.0
    MONTHLY_COST_LIMIT_USD: float = 50.0
    STUDENT_LIMIT_MULTIPLIER: float = 0.3
    FACULTY_LIMIT_MULTIPLIER: float = 0.6
    ADMIN_LIMIT_MULTIPLIER: float = 1.0
    FALLBACK_THRESHOLD_PERCENT: int = 90

    # ─── Caching ────────────────────────────────────────────
    CACHE_BACKEND: Literal["memory", "redis"] = "memory"
    CACHE_TTL_SECONDS: int = 300
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── Web Search ─────────────────────────────────────────
    WEB_SEARCH_PROVIDER: Literal[
        "duckduckgo", "tavily", "serpapi"
    ] = "duckduckgo"
    WEB_SEARCH_ENABLED: bool = True
    WEB_SEARCH_MAX_RESULTS: int = 5
    TAVILY_API_KEY: str = ""
    SERPAPI_API_KEY: str = ""

    # ─── Google Sheets ──────────────────────────────────────
    GOOGLE_SHEETS_ENABLED: bool = False
    GOOGLE_SERVICE_ACCOUNT_FILE: str = ""
    GOOGLE_SERVICE_ACCOUNT_JSON_B64: str = ""

    # ─── CORS ───────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v

    # ─── Scheduler ──────────────────────────────────────────
    SCHEDULER_ENABLED: bool = True
    DEADLINE_CHECK_INTERVAL_MINUTES: int = 30
    AUTO_RECOVER_EXTERNAL_LLM: bool = True
    RECOVERY_CHECK_INTERVAL_MINUTES: int = 10

    # ─── Security ───────────────────────────────────────────
    BCRYPT_ROUNDS: int = 12
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    MAX_UPLOAD_FILES_PER_REQUEST: int = 10
    ENABLE_AUDIT_LOGGING: bool = True

    # ─── Chunking ───────────────────────────────────────────
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # ─── Retrieval ──────────────────────────────────────────
    TOP_K_RESULTS: int = 5
    SIMILARITY_THRESHOLD: float = 0.3
    SUFFICIENT_CONTEXT_THRESHOLD: float = 0.6  # above this → skip web search

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton — import this everywhere."""
    return Settings()


settings = get_settings()
