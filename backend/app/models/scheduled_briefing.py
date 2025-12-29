"""ScheduledBriefing model for scheduled daily briefings."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, JSON, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ScheduledBriefing(Base):
    """Scheduled daily briefing configuration."""
    
    __tablename__ = "scheduled_briefings"
    
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
    
    # Configuration
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="User-friendly name for this schedule",
    )
    topic_ids: Mapped[list] = mapped_column(
        JSON,
        default=list,
        doc="List of topic IDs to include in the briefing",
    )
    schedule_time: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Time to generate briefing (HH:MM format in user's timezone)",
    )
    schedule_days: Mapped[list] = mapped_column(
        JSON,
        default=list,
        doc="Days of week to run (0=Monday, 6=Sunday)",
    )
    
    # Notifications
    notification_methods: Mapped[list] = mapped_column(
        JSON,
        default=list,
        doc="Notification methods: ['email', 'webhook']",
    )
    email_recipients: Mapped[list] = mapped_column(
        JSON,
        default=list,
        doc="List of email addresses to notify",
    )
    webhook_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Webhook URL for notifications",
    )
    
    # Settings
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        doc="Whether this schedule is enabled",
    )
    max_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=5,
        doc="Target duration in minutes",
    )
    resend_api_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Resend API key (optional, uses global if not set)",
    )
    
    # Tracking
    last_generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        doc="Last time a briefing was generated from this schedule",
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    # Cast assignment
    cast_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("casts.id"),
        nullable=True,
        doc="Cast used for scheduled briefings (uses default if not set)",
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="scheduled_briefings")
    cast: Mapped[Optional["Cast"]] = relationship("Cast", foreign_keys=[cast_id])
    
    def __repr__(self) -> str:
        return f"<ScheduledBriefing(id={self.id}, name={self.name}, active={self.is_active})>"
