"""Profile model for multi-user profiles."""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.topic import Topic
    from app.models.briefing import Briefing
    from app.models.cast import Cast
    from app.models.scheduled_briefing import ScheduledBriefing


class Profile(Base):
    """Profile model for sub-profiles under a user account."""
    
    __tablename__ = "profiles"
    
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
    
    # Profile details
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Display name for the profile, used for personalization in briefings (max 50 characters)",
    )
    color: Mapped[str] = mapped_column(
        String(7),
        default="#e85d04",  # App accent color
        doc="Hex color for the profile avatar",
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        doc="Whether this is the admin profile (cannot be deleted)",
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
    user: Mapped["User"] = relationship("User", back_populates="profiles")
    topics: Mapped[list["Topic"]] = relationship(
        "Topic",
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    briefings: Mapped[list["Briefing"]] = relationship(
        "Briefing",
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    casts: Mapped[list["Cast"]] = relationship(
        "Cast",
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    scheduled_briefings: Mapped[list["ScheduledBriefing"]] = relationship(
        "ScheduledBriefing",
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, name={self.name}, is_admin={self.is_admin})>"

