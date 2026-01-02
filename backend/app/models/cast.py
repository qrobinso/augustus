"""Cast and CastMember models for custom podcast casts."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Cast(Base):
    """Custom cast configuration for podcast hosts."""
    
    __tablename__ = "casts"
    
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
    
    # Cast configuration
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Name of the cast",
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(2000),
        nullable=True,
        doc="Description of how the cast works",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        doc="Whether this is the default cast for the user",
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
    user: Mapped["User"] = relationship("User", back_populates="casts")
    members: Mapped[list["CastMember"]] = relationship(
        "CastMember",
        back_populates="cast",
        cascade="all, delete-orphan",
        order_by="CastMember.order",
    )
    
    def __repr__(self) -> str:
        return f"<Cast(id={self.id}, name={self.name}, is_default={self.is_default})>"


class CastMember(Base):
    """Individual member of a cast."""
    
    __tablename__ = "cast_members"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    cast_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("casts.id"),
        nullable=False,
    )
    
    # Member configuration
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Name of the cast member (e.g., 'Alex', 'Sam')",
    )
    voice_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Voice ID from TTS provider",
    )
    personality: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Personality type (e.g., 'Casual', 'Analytical', 'Professional')",
    )
    order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Position in cast (0, 1, 2)",
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    
    # Relationships
    cast: Mapped["Cast"] = relationship("Cast", back_populates="members")
    
    def __repr__(self) -> str:
        return f"<CastMember(id={self.id}, name={self.name}, voice_id={self.voice_id}, order={self.order})>"




















