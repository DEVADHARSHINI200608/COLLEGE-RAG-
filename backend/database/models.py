"""
SQLAlchemy models — the single source of truth for the database schema.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, time
from typing import List, Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, Time, JSON, Enum as SAEnum,
    ARRAY, UniqueConstraint, Index, func
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, INET
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.types import TypeDecorator, String as SAString
import enum


# ─── SQLite-compatible UUID type ────────────────────────────────────────
class UUID(TypeDecorator):
    """Platform-independent UUID type. Uses PostgreSQL UUID, SQLite TEXT."""
    impl = SAString(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value)


# ─── Enums ──────────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    FACULTY = "FACULTY"
    ADMIN = "ADMIN"


class Classification(str, enum.Enum):
    CONFIDENTIAL = "CONFIDENTIAL"
    NON_CONFIDENTIAL = "NON_CONFIDENTIAL"


class SourceType(str, enum.Enum):
    PDF = "PDF"
    CSV = "CSV"
    XLSX = "XLSX"
    DOC = "DOC"
    DOCX = "DOCX"
    PPT = "PPT"
    PPTX = "PPTX"
    TXT = "TXT"
    MARKDOWN = "MARKDOWN"
    URL = "URL"
    GOOGLE_SHEETS = "GOOGLE_SHEETS"
    DATABASE = "DATABASE"


class SourceStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    DELETED = "DELETED"


class DeadlineStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class APIStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    API_UNAVAILABLE = "API_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    LOCAL_FALLBACK = "LOCAL_FALLBACK"
    ERROR = "ERROR"


# ─── Base ───────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ─── Users ──────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(Text, nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default=UserRole.STUDENT)
    department = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    uploaded_sources = relationship("Source", back_populates="uploader", foreign_keys="Source.uploaded_by")
    owned_sources = relationship("Source", back_populates="owner", foreign_keys="Source.owner_id")
    api_usages = relationship("APIUsage", back_populates="user")
    deadlines_created = relationship("Deadline", back_populates="creator")
    notifications = relationship("Notification", back_populates="recipient")
    audit_logs = relationship("AuditLog", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")


# ─── Sources ────────────────────────────────────────────────────────────
class Source(Base):
    __tablename__ = "sources"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    source_name = Column(String(500), nullable=False)
    source_type = Column(String(50), nullable=False)
    classification = Column(String(20), nullable=False, default=Classification.NON_CONFIDENTIAL)

    # Flags
    is_standard_resource = Column(Boolean, default=False)
    is_student_uploaded = Column(Boolean, default=False)
    is_external = Column(Boolean, default=False)

    # Ownership
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Organizational
    department = Column(String(100), nullable=True)
    version = Column(Integer, default=1)
    status = Column(String(20), default=SourceStatus.PENDING)

    # Access control (stored as JSON for SQLite compat)
    access_roles = Column(JSON, default=list)           # ["FACULTY", "ADMIN"]
    allowed_users = Column(JSON, default=list)          # [user_id, ...]
    allowed_departments = Column(JSON, default=list)    # ["IT", "CSE"]

    # Storage
    file_path = Column(Text, nullable=True)             # Local path or S3 key
    external_url = Column(Text, nullable=True)
    google_sheet_id = Column(String(200), nullable=True)

    # Ingestion metadata
    chunk_count = Column(Integer, default=0)
    file_size_bytes = Column(Integer, nullable=True)
    content_hash = Column(String(64), nullable=True)    # SHA-256 for dedup

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="owned_sources", foreign_keys=[owner_id])
    uploader = relationship("User", back_populates="uploaded_sources", foreign_keys=[uploaded_by])


# ─── Chat Sessions ──────────────────────────────────────────────────────
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")


# ─── Chat Messages ──────────────────────────────────────────────────────
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)           # "user" | "assistant"
    content = Column(Text, nullable=False)
    sources_used = Column(JSON, default=list)           # [{source_id, source_name, classification}]
    model_used = Column(String(100), nullable=True)     # "gpt-4o-mini" | "llama3.2"
    is_local_model = Column(Boolean, default=False)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


# ─── Deadlines ──────────────────────────────────────────────────────────
class Deadline(Base):
    __tablename__ = "deadlines"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    deadline_date = Column(Date, nullable=False)
    deadline_time = Column(Time, nullable=False)
    timezone = Column(String(100), default="Asia/Kolkata")
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    target_group = Column(String(100), nullable=True)
    target_source_id = Column(String(36), ForeignKey("sources.id"), nullable=True)
    master_list_source_id = Column(String(36), ForeignKey("sources.id"), nullable=True)
    response_source_id = Column(String(36), ForeignKey("sources.id"), nullable=True)
    missing_count = Column(Integer, nullable=True)
    missing_names = Column(JSON, default=list)
    status = Column(String(20), default=DeadlineStatus.ACTIVE)
    notification_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User", back_populates="deadlines_created")
    notifications = relationship("Notification", back_populates="deadline")


# ─── Notifications ──────────────────────────────────────────────────────
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    deadline_id = Column(String(36), ForeignKey("deadlines.id"), nullable=True)
    recipient_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime, default=datetime.utcnow)

    deadline = relationship("Deadline", back_populates="notifications")
    recipient = relationship("User", back_populates="notifications")


# ─── API Usage ──────────────────────────────────────────────────────────
class APIUsage(Base):
    __tablename__ = "api_usage"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    provider = Column(String(100), nullable=False)      # "openai" | "gemini" | "ollama"
    model = Column(String(100), nullable=False)
    request_tokens = Column(Integer, default=0)
    response_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    status = Column(String(50), nullable=False, default=APIStatus.SUCCESS)
    is_fallback = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_usages")


# ─── Audit Logs ─────────────────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(200), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(36), nullable=True)
    ip_address = Column(String(45), nullable=True)      # IPv4/IPv6
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")


# ─── System Settings ────────────────────────────────────────────────────
class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    key = Column(String(200), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    value_type = Column(String(20), default="string")   # string | int | float | bool | json
    description = Column(Text, nullable=True)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
