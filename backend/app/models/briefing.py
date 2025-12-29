"""Briefing model for daily audio briefings."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, JSON, ForeignKey, Integer, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Briefing(Base):
    """Daily audio briefing model."""
    
    __tablename__ = "briefings"
    
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
    
    # Content
    title: Mapped[str] = mapped_column(String(500), default="Daily Briefing")
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Audio
    audio_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Extra data (renamed from metadata which is reserved)
    extra_data: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        doc="Additional data: voices used, sources, topics covered",
    )
    sources: Mapped[list] = mapped_column(
        JSON,
        default=list,
        doc="List of sources used in this briefing",
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        doc="Status: pending, generating, completed, failed",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Listen tracking
    listened: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        doc="Whether the user has listened to this briefing",
    )
    listened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        doc="When the user marked this as listened",
    )
    playback_position: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        doc="Last playback position in seconds (for resume functionality)",
    )
    
    # Favorite tracking
    favorite: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        doc="Whether the user has favorited this briefing",
    )
    
    # Timestamps
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    
    # Cast assignment
    cast_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("casts.id"),
        nullable=True,
        doc="Cast used for this briefing (uses default if not set)",
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="briefings")
    cast: Mapped[Optional["Cast"]] = relationship("Cast", foreign_keys=[cast_id])
    
    def __repr__(self) -> str:
        return f"<Briefing(id={self.id}, title={self.title}, status={self.status})>"
    
    @property
    def audio_url(self) -> Optional[str]:
        """Get the audio URL for this briefing."""
        if self.audio_filename:
            return f"/audio/{self.audio_filename}"
        return None
