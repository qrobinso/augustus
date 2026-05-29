"""API key and MCP audit log models."""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, Integer, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.profile import Profile


class ApiKey(Base):
    """API key for an external agent (e.g. an MCP client) to act as a profile."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
    )
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id"),
        nullable=False,
        doc="Profile this key acts as",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Human-friendly label",
    )
    key_prefix: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
        doc="First chars of the raw key, displayed in UI",
    )
    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        doc="SHA-256 hash of the raw key",
    )
    enabled_tools: Mapped[Optional[list]] = mapped_column(
        JSON,
        default=None,
        doc="List of MCP tool names enabled for this key. None = all enabled.",
    )

    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_client: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["Profile"] = relationship("Profile")

    __table_args__ = (
        Index("idx_api_keys_user_id", "user_id"),
        Index("idx_api_keys_profile_id", "profile_id"),
    )


class McpAuditLog(Base):
    """Audit log entry for an MCP tool invocation."""

    __tablename__ = "mcp_audit_log"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    api_key_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="success | error | denied",
    )
    error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    client: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    args_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    __table_args__ = (
        Index("idx_mcp_audit_api_key_id", "api_key_id"),
        Index("idx_mcp_audit_created_at", "created_at"),
    )
