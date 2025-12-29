"""User model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """User model for storing user preferences and settings."""
    
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), default="Default User")
    
    # Preferences stored as JSON
    preferences: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        doc="User preferences including languages, interests, TTS voice settings",
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
    
    # Relationships
    briefings: Mapped[list["Briefing"]] = relationship(
        "Briefing",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    custom_sites: Mapped[list["CustomSite"]] = relationship(
        "CustomSite",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    topics: Mapped[list["Topic"]] = relationship(
        "Topic",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    scheduled_briefings: Mapped[list["ScheduledBriefing"]] = relationship(
        "ScheduledBriefing",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    casts: Mapped[list["Cast"]] = relationship(
        "Cast",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, name={self.name})>"

